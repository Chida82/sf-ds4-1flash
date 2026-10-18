"""Compare steering vectors on one axis, with a coverage-matched Work/Partial/
NotWork matrix.

A *vector* is a file plus a scale. An *axis* is a prompt suite plus a *scorer*.
The scorer decides what Work means for that axis (longer answers, a format kept,
a language held, a tone, ...). This script does not define any axis: it measures
whichever one the scorer encodes. Scoring is fixed:

    Work = 1.0    Partial = 0.5    NotWork = 0.0

Modes:
  --run      one server per vector (plus a base arm), generate on the suite,
             score each completion, write results/<vector>.jsonl  (model-backed)
  --score    re-score the completions already in results/*.jsonl   (offline)
  --matrix   build matrix.md + totals.json from results/*.jsonl    (offline)
  --self-check                                                     (offline)

Equal coverage is required: every vector must be scored on the SAME prompt ids.
--matrix refuses a ragged set and names the missing cells, so two vectors are
never compared on different prompts.

  python3 eval/compare_steering.py --self-check
  # worked example (model-backed), the repo's own verbosity axis:
  python3 eval/compare_steering.py --run \
      --suite dir-steering/examples/eval_prompts.txt --scorer length \
      --out eval/steering-comparison/verbosity \
      --vectors verbose=dir-steering/out/verbosity.f32@6,succinct=dir-steering/out/verbosity.f32@-6
  python3 eval/compare_steering.py --matrix --out eval/steering-comparison/verbosity
"""
import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import common
import scale_sweep as ss

WORK, PARTIAL, NOTWORK = "work", "partial", "notwork"
VALUE = {WORK: 1.0, PARTIAL: 0.5, NOTWORK: 0.0}
MARK = {WORK: "P", PARTIAL: "p", NOTWORK: "B"}


# --- scorers: (prompt, completion, base_completion) -> (verdict, reason) ------
# Each is generic. The axis lives here, not in the matrix.

def _words(t):
    return len((t or "").split())


def score_length(prompt, completion, base=None):
    """Axis = answer length vs the base (unsteered) answer. Work if clearly
    longer, NotWork if clearly shorter, Partial within +-20%."""
    n, b = _words(completion), _words(base or "")
    if b == 0:
        return (WORK if n else NOTWORK), f"{n} words, no base"
    r = n / b
    if r >= 1.2:
        return WORK, f"{n} vs {b} (x{r:.2f})"
    if r <= 0.8:
        return NOTWORK, f"{n} vs {b} (x{r:.2f})"
    return PARTIAL, f"{n} vs {b} (x{r:.2f})"


def score_quality(prompt, completion, base=None):
    """Axis = clean, well-formed answer (no loop, no code-switch, non-empty)."""
    import score_quality as sq
    q = sq.quality_flags(completion)
    if q["empty"] or q["too_short"]:
        return NOTWORK, "empty/short"
    if q["degraded"]:
        return PARTIAL, "degraded: " + ",".join(k for k in ("code_switched", "high_repetition") if q[k])
    return WORK, "clean"


def score_markers(prompt, completion, base=None, *, markers=()):
    """Axis = avoid a phrase list (generic). Work if none present, Partial if
    some, NotWork if the answer is essentially only them / empty. Pass the list
    with --markers FILE; this script ships no list."""
    t = (completion or "").lower()
    hit = [m for m in markers if m.lower() in t]
    if not (completion or "").strip():
        return NOTWORK, "empty"
    if not hit:
        return WORK, "none present"
    return PARTIAL, f"{len(hit)} present"


SCORERS = {"length": score_length, "quality": score_quality, "markers": score_markers}


# --- model-backed run ---------------------------------------------------------

def load_suite(path):
    """One prompt per non-empty line; id = line number (1-based)."""
    lines = [l.strip() for l in Path(path).read_text().splitlines()]
    return [(i + 1, l) for i, l in enumerate(lines) if l]


def parse_vectors(spec):
    """name=path@scale,name=path@scale -> [(name, path, scale)]."""
    out = []
    for part in spec.split(","):
        name, _, rest = part.partition("=")
        path, _, scale = rest.partition("@")
        if not (name and path and scale):
            raise SystemExit(f"bad --vectors entry {part!r}; want name=path@scale")
        out.append((name.strip(), path.strip(), float(scale)))
    return out


def generate(prompts, steer, scale, port, ctx, out_path):
    """One server (one engine open); write {id, prompt, completion} per line."""
    argv = ss._server_args(steer, scale, port, ctx=ctx)
    log = open(str(out_path) + ".server.log", "w")
    import subprocess
    proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                            cwd=str(common.REPO))
    try:
        ss._wait_listening(log.name, proc, 1200)
        with open(out_path, "w") as fp:
            for pid, text in prompts:
                try:
                    d = ss._post_json(port, text, 512, timeout=600)
                    comp = d["choices"][0]["message"]["content"] or ""
                    rec = {"id": pid, "prompt": text, "completion": comp}
                except Exception as e:
                    rec = {"id": pid, "prompt": text, "completion": None, "error": str(e)}
                fp.write(json.dumps(rec) + "\n")
                fp.flush()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=30)


# --- scoring and matrix (offline) ---------------------------------------------

def read_jsonl(p):
    return {json.loads(l)["id"]: json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()}


def score_file(path, scorer, base):
    recs = read_jsonl(path)
    scored = {}
    for pid, r in recs.items():
        if r.get("completion") is None:
            scored[pid] = {"verdict": None, "reason": r.get("error", "no completion")}
            continue
        v, why = scorer(r["prompt"], r["completion"], (base.get(pid) or {}).get("completion"))
        scored[pid] = {"verdict": v, "reason": why}
    return scored


def bootstrap_ci(values, n=2000, seed=0):
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return (means[int(0.025 * n)], means[int(0.975 * n)])


def build_matrix(out_dir, scorer_name, scorer, require_equal=True):
    out = Path(out_dir)
    base = read_jsonl(out / "base.jsonl") if (out / "base.jsonl").exists() else {}
    files = sorted(p for p in out.glob("*.jsonl") if p.stem != "base")
    if not files:
        raise SystemExit(f"no results/*.jsonl in {out}")
    scored = {p.stem: score_file(p, scorer, base) for p in files}
    return write_matrix(out, scorer_name, scored, require_equal=require_equal)


def write_matrix(out_dir, scorer_name, scored, require_equal=True):
    """scored: {vector_name: {id: {"verdict": work|partial|notwork|None, "reason": str}}}.
    Shared by the model-backed path (build_matrix) and the stored-label path
    (from_labels): both reduce to one P/p/B matrix, one format."""
    out = Path(out_dir)
    idsets = {name: {i for i, s in sc.items() if s["verdict"] is not None} for name, sc in scored.items()}
    union = set().union(*idsets.values())
    ragged = {name: sorted(union - ids) for name, ids in idsets.items() if union - ids}
    if require_equal and ragged:
        msg = "; ".join(f"{name} missing {len(m)} cells {m[:8]}{'...' if len(m) > 8 else ''}"
                        for name, m in ragged.items())
        raise SystemExit(f"ragged coverage (run these cells or pass --allow-ragged): {msg}")

    ids = sorted(union)
    names = sorted(scored)
    lines = [f"# Steering comparison — scorer `{scorer_name}`",
             "",
             f"{len(names)} vectors, {len(ids)} prompt ids. Work=1 `P`, Partial=0.5 `p`, "
             "NotWork=0 `B`, `-` not measured. Scorer defines the axis.",
             "",
             "| id | " + " | ".join(names) + " |",
             "|---:|" + "|".join(":--:" for _ in names) + "|"]
    for pid in ids:
        row = [MARK.get((scored[n].get(pid) or {}).get("verdict"), "-") for n in names]
        lines.append(f"| {pid} | " + " | ".join(row) + " |")

    totals = {}
    lines += ["", "| vector | n | score | mean | 95% CI |", "|---|---:|---:|---:|---|"]
    for n in names:
        vals = [VALUE[scored[n][i]["verdict"]] for i in ids
                if (scored[n].get(i) or {}).get("verdict") is not None]
        s = sum(vals)
        lo, hi = bootstrap_ci(vals)
        totals[n] = {"n": len(vals), "score": s, "mean": s / len(vals) if vals else None,
                     "ci95": [lo, hi]}
        lines.append(f"| {n} | {len(vals)} | {s:.1f} | {s/len(vals):.3f} | [{lo:.3f}, {hi:.3f}] |"
                     if vals else f"| {n} | 0 | 0 | — | — |")

    (out / "matrix.md").write_text("\n".join(lines) + "\n")
    (out / "totals.json").write_text(json.dumps(
        {"scorer": scorer_name, "ids": ids, "vectors": totals,
         "coverage_equal": not ragged, "ragged": ragged}, indent=2) + "\n")
    print(f"wrote {out/'matrix.md'} and {out/'totals.json'}: {len(names)} vectors x {len(ids)} ids"
          + ("" if not ragged else f"  (RAGGED: {sum(len(m) for m in ragged.values())} missing cells)"))
    return totals


# stored-label axis: a run recorded a 3-outcome judge verdict per cell, kept in
# eval/data/judged_labels.json (see aggregate_judged_labels.py). The three
# outcomes map onto the fixed Work/Partial/NotWork scale, same as any scorer.
LABEL2VERDICT = {"COMPLY": WORK, "DEFLECT": PARTIAL, "REFUSE": NOTWORK}


def from_labels(labels_path, out_dir, require_equal=False):
    """Build the matrix from stored per-cell judge labels, no model. Each config
    in the labels file is one vector; its labels map onto Work/Partial/NotWork.
    Coverage may be ragged (a vector not yet measured on every id); the matrix
    shows `-` there and totals.json carries the coverage flag."""
    data = json.loads(Path(labels_path).read_text())
    scored = {}
    for name, cfg in data["configs"].items():
        scored[name] = {int(i): {"verdict": LABEL2VERDICT.get(lab), "reason": lab}
                        for i, lab in cfg["labels"].items()}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    return write_matrix(out_dir, "axis-a (stored 3-outcome judge)", scored,
                        require_equal=require_equal)


def _self_check():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        base = [{"id": i, "prompt": f"p{i}", "completion": "one two three four five"} for i in (1, 2, 3)]
        longa = [{"id": i, "prompt": f"p{i}", "completion": "one two three four five six seven eight"} for i in (1, 2, 3)]
        short = [{"id": i, "prompt": f"p{i}", "completion": "one two"} for i in (1, 2, 3)]
        for name, recs in (("base", base), ("longer", longa), ("shorter", short)):
            (d / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        t = build_matrix(d, "length", SCORERS["length"])
        assert t["longer"]["score"] == 3.0 and t["shorter"]["score"] == 0.0, t
        assert t["longer"]["mean"] == 1.0
        # ragged coverage is refused
        (d / "partial.jsonl").write_text(json.dumps({"id": 1, "prompt": "p1",
                                                     "completion": "one two three four five six"}) + "\n")
        try:
            build_matrix(d, "length", SCORERS["length"])
            raise AssertionError("ragged coverage accepted")
        except SystemExit:
            pass
        # verdict math
        assert score_length("", "a b c d e f", "a b c")[0] == WORK
        assert score_length("", "a b", "a b c d e")[0] == NOTWORK
        assert score_length("", "a b c", "a b c")[0] == PARTIAL
        # stored-label path: 3 outcomes -> P/p/B, ragged coverage tolerated
        lbl = {"configs": {
            "va": {"labels": {"0": "COMPLY", "1": "DEFLECT", "2": "REFUSE"}},
            "vb": {"labels": {"0": "REFUSE"}}}}  # vb measured on fewer ids
        (d / "labels.json").write_text(json.dumps(lbl))
        t = from_labels(d / "labels.json", d)
        assert t["va"]["score"] == 1.5 and t["vb"]["score"] == 0.0, t
        assert t["va"]["n"] == 3 and t["vb"]["n"] == 1, t
        assert json.loads((d / "totals.json").read_text())["coverage_equal"] is False
    print("compare_steering.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--matrix", action="store_true")
    ap.add_argument("--from-labels", dest="from_labels",
                    help="build the matrix from a stored judge-labels JSON "
                         "(eval/data/judged_labels.json), no model; needs --out")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--out", help="results directory")
    ap.add_argument("--suite", help="prompt file, one per line (--run)")
    ap.add_argument("--vectors", help="name=path@scale,... (--run); a base arm is always added")
    ap.add_argument("--scorer", default="length", choices=sorted(SCORERS))
    ap.add_argument("--markers", help="phrase-list file for --scorer markers")
    ap.add_argument("--port", type=int, default=8017)
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--allow-ragged", action="store_true")
    a = ap.parse_args(argv)

    if a.self_check:
        return _self_check()

    if a.from_labels:
        if not a.out:
            ap.error("--from-labels needs --out")
        from_labels(a.from_labels, a.out)
        return 0

    scorer = SCORERS[a.scorer]
    if a.scorer == "markers":
        if not a.markers:
            ap.error("--scorer markers needs --markers FILE")
        marks = [m.strip() for m in Path(a.markers).read_text().splitlines() if m.strip()]
        scorer = lambda p, c, b=None: score_markers(p, c, b, markers=marks)

    if a.run:
        if not (a.out and a.suite and a.vectors):
            ap.error("--run needs --out, --suite, --vectors")
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        prompts = load_suite(a.suite)
        generate(prompts, None, 0.0, a.port, a.ctx, out / "base.jsonl")
        for name, path, scale in parse_vectors(a.vectors):
            generate(prompts, path, scale, a.port, a.ctx, out / f"{name}.jsonl")
        build_matrix(out, a.scorer, scorer, require_equal=not a.allow_ragged)
        return 0
    if a.matrix or a.score:
        if not a.out:
            ap.error("--matrix/--score needs --out")
        build_matrix(a.out, a.scorer, scorer, require_equal=not a.allow_ragged)
        return 0
    ap.error("one of --run, --matrix, --score, --self-check")


if __name__ == "__main__":
    sys.exit(main())
