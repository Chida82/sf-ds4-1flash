"""Collateral-quality check of the axis-a finalist fused@7 (TODO 0c item 4, axis B/C).
Over-refusal on XSTest-safe (250 safe prompts that LOOK unsafe): a refusal-removal vector
must not start refusing safe prompts more than the base. Per prompt it generates the base and
the fused@7 arm, stores each answer, and (model-less) scores refusal (score_keyword) and quality
flags (score_quality: code-switch, loops, implausible). Resumable per prompt+arm; a run does not
start a generation it cannot end before DEADLINE (epoch seconds, env).

  DEADLINE=$(($(date +%s)+4200)) SF_EVAL_CACHE_EXPERTS=62GB caffeinate -i \
    python3 eval/collateral.py --run >> eval/out/stages/collateral.log 2>&1 &
  python3 eval/collateral.py --analyze      # model-less; -> eval/steering-comparison/collateral.md
  python3 eval/collateral.py --self-check

Axis D (capability / MMLU via the eval binary) is the multi-hour job and is left out of this
window; it is a separate run.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import datasets_overrefusal as dor  # noqa: E402
import generate  # noqa: E402
import score_keyword  # noqa: E402
import score_quality  # noqa: E402

FUSED = "dir-steering/vectors/v41-fused-msuiche-audreyt-denoise.f32"
SCALE = 7.0
OUT = Path("eval/out-collateral")
ARMS = {"base": None, "fused7": FUSED}          # name -> steer path (None = base)
MAX_TOKENS = 384                                # benign answers; nothink keeps it fast
PER_GEN_MIN = float(os.environ.get("COLLATERAL_GEN_MIN", "1.2"))  # deadline guard estimate


def _past_deadline(deadline):
    return deadline and time.time() + PER_GEN_MIN * 60 > deadline


def run():
    deadline = int(os.environ.get("DEADLINE", "0")) or None
    prompts = dor.load_xstest_safe()
    for name in ARMS:
        (OUT / name).mkdir(parents=True, exist_ok=True)
    print(f"{time.strftime('%F %T')} collateral: {len(prompts)} XSTest-safe prompts, "
          f"arms {list(ARMS)}, deadline {deadline or 'none'}", flush=True)
    done = 0
    for i, p in enumerate(prompts):
        for name, steer in ARMS.items():
            f = OUT / name / f"{i}.json"
            if f.exists():
                continue
            if _past_deadline(deadline):
                print(f"{time.strftime('%F %T')} collateral: stop before deadline "
                      f"(prompt {i} arm {name}); resumable", flush=True)
                return
            rec = generate.gen(p, steer=steer, residual=SCALE if steer else 0.0,
                               think=False, max_tokens=MAX_TOKENS)
            common.save_json(f, {"i": i, "prompt": p, "arm": name,
                                 "completion": rec["completion"], "returncode": rec["returncode"]})
            done += 1
        if (i + 1) % 10 == 0:
            print(f"{time.strftime('%F %T')} collateral: through prompt {i + 1}/{len(prompts)} "
                  f"({done} new generations)", flush=True)
    print(f"{time.strftime('%F %T')} collateral: finished ({done} new generations)", flush=True)


def _load(name):
    out = {}
    for f in (OUT / name).glob("*.json"):
        r = json.loads(f.read_text())
        if r.get("completion", "").strip() and r.get("returncode") == 0:
            out[r["i"]] = r["completion"]
    return out


def analyze(out_md="eval/steering-comparison/collateral.md"):
    arms = {name: _load(name) for name in ARMS}
    ids = sorted(set.intersection(*(set(a) for a in arms.values())))
    L = [f"# Collateral check — fused@7 vs base, XSTest-safe (over-refusal)", "",
         f"prompts finished in both arms: {len(ids)}", ""]
    if not ids:
        Path(out_md).write_text("\n".join(L + ["nothing finished yet"]) + "\n")
        return "\n".join(L + ["nothing finished yet"])
    ref = {name: {i: score_keyword.is_refusal(arms[name][i]) for i in ids} for name in ARMS}
    qf = {name: {i: score_quality.quality_flags(arms[name][i]) for i in ids} for name in ARMS}
    L += ["These are SAFE prompts: refusing one is the collateral cost. Lower refusal = better.",
          "", "| arm | refusals | refusal rate | code-switch | high-repetition | too-short |",
          "|---|---:|---:|---:|---:|---:|"]
    for name in ARMS:
        nr = sum(ref[name].values())
        cs = sum(f["code_switched"] for f in qf[name].values())
        hr = sum(f["high_repetition"] for f in qf[name].values())
        ts = sum(f["too_short"] for f in qf[name].values())
        L.append(f"| {name} | {nr} | {nr / len(ids):.3f} | {cs} | {hr} | {ts} |")
    extra = [i for i in ids if ref["fused7"][i] and not ref["base"][i]]
    gained = [i for i in ids if not ref["fused7"][i] and ref["base"][i]]
    L += ["", f"safe prompts fused@7 refuses but base does NOT (new over-refusal): {len(extra)}",
          f"safe prompts base refuses but fused@7 does not: {len(gained)}", ""]
    for i in extra[:12]:
        L.append(f"- [{i}] {arms['base'][i][:70]!r}")
    txt = "\n".join(L)
    Path(out_md).write_text(txt + "\n")
    return txt


def _self_check():
    # quality_flags + is_refusal shape; analyze with a tiny fake store in a temp dir.
    import tempfile
    global OUT
    d = Path(tempfile.mkdtemp())
    OUT = d
    for name in ARMS:
        (d / name).mkdir()
    (d / "base" / "0.json").write_text(json.dumps({"i": 0, "prompt": "p", "arm": "base",
        "completion": "Sure, here is how.", "returncode": 0}))
    (d / "fused7" / "0.json").write_text(json.dumps({"i": 0, "prompt": "p", "arm": "fused7",
        "completion": "I'm sorry, but I cannot help with that.", "returncode": 0}))
    txt = analyze(str(d / "out.md"))
    assert "prompts finished in both arms: 1" in txt, txt
    assert "new over-refusal): 1" in txt, txt
    print("collateral.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", action="store_true")
    g.add_argument("--analyze", action="store_true")
    g.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if a.run:
        run()
        return 0
    print(analyze())
    return 0


if __name__ == "__main__":
    sys.exit(main())
