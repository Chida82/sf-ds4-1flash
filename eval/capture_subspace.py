"""Fold capture for the refusal-subspace study: base model, many prompts, 20-token incipit.

Per prompt, one server request (think off, max_tokens N). Three (40, 5120) f32 files, one row per
layer, from the same site as capture_fold.py: `rows_<idx>` the decision block (last prompt token),
`gen_<idx>` the first generated token, `pmean_<idx>` the mean over the prompt tokens; the first
N tokens and their keyword refusal flag go to `<idx>.json`. Order: alpaca benign (b<k>), the 44
study ids, then the rest of the union shuffled (seed). Stops when --target harmful prompts
refused in the incipit, or before DEADLINE (epoch seconds, env). Resumable per prompt.
The model comes from SF_EVAL_MODEL (common.MODEL): never move the default symlink for this.

  DEADLINE=... SF_EVAL_MODEL=gguf/<file> caffeinate -i python3 eval/capture_subspace.py \
      --out eval/out-subspace-1017/capture >> eval/out/stages/capture-subspace.log 2>&1
  python3 eval/capture_subspace.py --self-check
"""
import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import datasets_benign  # noqa: E402
import extract_floor_direction as efd  # noqa: E402
import scale_sweep as ss  # noqa: E402
import score_keyword  # noqa: E402

PORT = 8015
STUDY = list(range(30)) + [372, 426, 468, 544, 612, 676, 943, 955, 1006, 1081, 1123, 1126, 1141, 1150]
PER_PROMPT_SEC = 12  # deadline guard


def read_decision_at(dump, usage):
    """-> (decision, first_generated, prompt_mean), each (40, 5120). Decision = block
    prefilled-1 (rule 2 of capture_fold); first_generated = block prefilled (None when the
    dump stops at the decision); prompt_mean = mean of the prefilled blocks. The dump may hold
    up to completion_tokens+1 evaluated blocks after the prompt."""
    a = np.fromfile(dump, dtype=np.float32)
    blocks, rem = divmod(a.size, efd.N_LAYERS * efd.D)
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    prefilled = usage["prompt_tokens"] - cached
    comp = usage.get("completion_tokens", 0)
    if rem or prefilled < 1 or not (prefilled <= blocks <= prefilled + comp + 1):
        raise RuntimeError(f"dump has {blocks} blocks (+{rem} floats); prefilled {prefilled}, "
                           f"completion {comp}")
    a = a.reshape(blocks, efd.N_LAYERS, efd.D)
    gen = a[prefilled] if blocks > prefilled else None
    return a[prefilled - 1], gen, a[:prefilled].mean(0)


def plan(records, benign, seed):
    rest = [i for i in range(len(records)) if i not in set(STUDY)]
    random.Random(seed).shuffle(rest)
    ents = [{"idx": f"b{k}", "class": "benign", "source": "alpaca", "text": t} for k, t in enumerate(benign)]
    ents += [{"idx": i, "class": "study" if i in set(STUDY) else "pool",
              "source": records[i]["source"], "text": records[i]["text"]} for i in STUDY + rest]
    return ents


def run(a):
    deadline = int(os.environ.get("DEADLINE", "0")) or None
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.external == "sorrybench":  # the external test set: idx s<question_id>, no benign, no union
        import datasets_sorrybench
        ents = [{"idx": f"s{r['id']}", "class": "sorrybench", "source": f"sorrybench-cat{r['category']}",
                 "text": r["text"]} for r in datasets_sorrybench.load_sorrybench_heldout()]
    else:
        records = efd.build_union()
        ents = plan(records, datasets_benign.load_alpaca_benign(a.benign), a.seed)
    done = {p.stem for p in out.glob("*.json") if p.stem != "manifest"}
    refused = sum(json.loads((out / f"{i}.json").read_text()).get("refusal", False)
                  for i in done if not i.startswith("b"))
    todo = [e for e in ents if str(e["idx"]) not in done]
    print(f"{time.strftime('%F %T')} capture-subspace: {len(ents)} planned, {len(done)} done "
          f"({refused} refused), model {common.MODEL}", flush=True)
    if a.dry_run or not todo:
        return 0
    argv = ss._server_args(None, 0.0, a.port, ctx=4096)
    dump = str(out / "dump.f32")
    env = dict(os.environ, DS4_V41_DUMP_STEER_INPUT=dump)
    n_new = 0
    with open(out / "server.log", "a") as log:
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, cwd=str(common.REPO), env=env)
        try:
            ss._wait_listening(log.name, proc, efd.OPEN_TIMEOUT)
            for e in todo:
                if refused >= a.target:
                    print(f"{time.strftime('%F %T')} capture-subspace: target {a.target} refused reached", flush=True)
                    break
                if deadline and time.time() + PER_PROMPT_SEC > deadline:
                    print(f"{time.strftime('%F %T')} capture-subspace: stop before deadline; resumable", flush=True)
                    break
                open(dump, "wb").close()
                try:
                    d = ss._post_json(a.port, e["text"], a.max_tokens, timeout=600)
                    rows, gen, pmean = read_decision_at(dump, d["usage"])
                except Exception as ex:
                    print(f"capture-subspace: {e['idx']}: {ex}", file=sys.stderr, flush=True)
                    continue
                text = d["choices"][0]["message"]["content"] or ""
                rec = {**{k: e[k] for k in ("idx", "class", "source")},
                       "text_sha256": hashlib.sha256(e["text"].encode()).hexdigest(),
                       "usage": d["usage"], "incipit": text, "has_gen": gen is not None,
                       "refusal": bool(score_keyword.is_refusal(text)) if e["class"] != "benign" else None}
                rows.astype(np.float32).tofile(out / f"rows_{e['idx']}.f32")      # decision row
                pmean.astype(np.float32).tofile(out / f"pmean_{e['idx']}.f32")    # mean over prompt tokens
                if gen is not None:
                    gen.astype(np.float32).tofile(out / f"gen_{e['idx']}.f32")    # first generated token
                common.save_json(out / f"{e['idx']}.json", rec)
                n_new += 1
                refused += bool(rec["refusal"])
                if n_new % 50 == 0:
                    print(f"{time.strftime('%F %T')} capture-subspace: +{n_new} ({refused} refused)", flush=True)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=30)
    if os.path.exists(dump):
        os.remove(dump)
    common.save_json(out / "manifest.json", {
        "site": "v41_attn_input_weighted_fold_post_engram", "row_rule": 2, "max_tokens": a.max_tokens,
        "model": common.MODEL, "server_argv": argv, "seed": a.seed,
        "n": len(list(out.glob("rows_*.f32"))), "refused": refused})
    print(f"{time.strftime('%F %T')} capture-subspace: finished, +{n_new} new, {refused} refused", flush=True)
    return 0


def _self_check():
    import tempfile
    b = efd.N_LAYERS * efd.D
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dump.f32"
        a = np.concatenate([np.full(b, float(t), np.float32) for t in range(5)])
        a.tofile(p)
        # 3 prompt tokens + 2 evaluated: decision = block 2, first generated = block 3, mean = 1
        r, g, m = read_decision_at(p, {"prompt_tokens": 3, "completion_tokens": 2})
        assert r.shape == (efd.N_LAYERS, efd.D) and r[0, 0] == 2.0 and g[0, 0] == 3.0 and m[0, 0] == 1.0
        # cached prefix of 1: prefilled 2 -> decision block 1
        r, g, m = read_decision_at(p, {"prompt_tokens": 3, "completion_tokens": 3,
                                       "prompt_tokens_details": {"cached_tokens": 1}})
        assert r[0, 0] == 1.0 and g[0, 0] == 2.0 and m[0, 0] == 0.5
        a[:3 * b].tofile(p)  # dump that stops at the decision: no generated block
        _, g, _ = read_decision_at(p, {"prompt_tokens": 3, "completion_tokens": 1})
        assert g is None
        a.tofile(p)
        try:
            read_decision_at(p, {"prompt_tokens": 3, "completion_tokens": 0}); raise AssertionError("too many blocks accepted")
        except RuntimeError:
            pass
    recs = [{"source": "s", "text": f"t{i}"} for i in range(1300)]
    ents = plan(recs, ["hi"], 1)
    assert ents[0]["idx"] == "b0" and ents[1]["idx"] == 0 and ents[44]["idx"] == 1150
    assert len(ents) == 1301 and len({str(e["idx"]) for e in ents}) == 1301
    print("capture_subspace.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="eval/out-subspace-1017/capture")
    ap.add_argument("--target", type=int, default=1000, help="stop after this many refused harmful prompts")
    ap.add_argument("--max-tokens", type=int, default=20)
    ap.add_argument("--benign", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1017)
    ap.add_argument("--external", choices=["sorrybench"], help="capture an external test set instead of the union")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    return _self_check() if a.self_check else run(a)


if __name__ == "__main__":
    sys.exit(main())
