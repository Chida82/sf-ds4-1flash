"""Third-source refusal direction from activations (Arditi/FailSpy, native V4.1 site).

Contrast the attention-input fold (DS4_V41_DUMP_STEER_INPUT) of harmful prompts that
RESIST msuiche (class A = survivors) against harmful prompts msuiche OPENS (class B),
both at BASE. The per-layer direction `unit(mean_A - mean_B)` is what distinguishes a
floor-resistant prompt from an openable one at the fold; removing it should move the
floor toward the openable region. This is NOT a msuiche/abliteration combination — it
is extracted from the model's own activations on these prompts.

One base server (no steering) with the dump env; one prompt at n=1 per request,
truncating the dump between requests and reading the last 40 rows (the decision
position, layers 0..39). Pure-python (diff-of-means needs no numpy).

  python3 eval/extract_floor_direction.py --out dir-steering/out/v41-floor-resist.f32
  python3 eval/extract_floor_direction.py --self-check
"""
import argparse
import array
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import common
import compose
import datasets_harmful as dh
import manifest
import scale_sweep as ss

PORT = 8014
D = 5120
N_LAYERS = 40          # DS4_N_LAYER - DS4_N_NEXTN_PREDICT; the dump writes one row per model layer
OPEN_TIMEOUT = 1200
ZERO_TOL = 1e-6  # a layer whose raw diff norm is below this is written as a zero row


def build_union():
    parts = [compose.tag(dh.load_advbench(), "advbench", "")]
    for loader, name in ((dh.load_harmbench, "harmbench"), (dh.load_strongreject, "strongreject")):
        try:
            parts.append(compose.tag(loader(), name, ""))
        except Exception as e:
            print(f"extract: skipping source: {e}", file=sys.stderr)
    return compose.dedup_tagged([r for p in parts for r in p])


def classes_from_discovery():
    per = json.loads(Path(common.OUT / "discover/A_v41-msuiche@5.json").read_text())["per_prompt"]
    A = [x["idx"] for x in per if x["survivor"]]
    B = [x["idx"] for x in per if x["base_refuse"] and not x["steered_refuse"] and not x["err"]]
    return A, B


def read_last_decision(dump_path):
    """Last 40 rows of the dump = the decision token's fold, layers 0..39."""
    raw = Path(dump_path).read_bytes()
    a = array.array("f"); a.frombytes(raw)
    rows = len(a) // D
    if rows < N_LAYERS or rows % N_LAYERS != 0:
        raise RuntimeError(f"dump has {rows} rows, not a multiple of {N_LAYERS}")
    base = (rows - N_LAYERS) * D
    return [a[base + il * D: base + (il + 1) * D] for il in range(N_LAYERS)]


def accumulate(idxs, records, dump_path, port, acc, n_layers):
    for i in idxs:
        open(dump_path, "wb").close()  # truncate before the request
        _ = ss._post(port, records[i]["text"], 1, timeout=600)
        rows = read_last_decision(dump_path)
        for il in range(n_layers):
            s = acc[il]; r = rows[il]
            for k in range(D):
                s[k] += r[k]


def extract(args):
    records = build_union()
    A, B = classes_from_discovery()
    # even sample of B to the requested count (balance the means; A stays whole)
    if args.b_count and len(B) > args.b_count:
        B = B[:: max(1, len(B) // args.b_count)][:args.b_count]
    nL = N_LAYERS
    print(f"class A (resist) {len(A)} · class B (open) {len(B)} · layers {nL} · out {args.out}")
    if args.dry_run:
        return 0

    dump = os.path.abspath(args.dump or "/tmp/sf-extract-dump.f32")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, DS4_V41_DUMP_STEER_INPUT=dump)
    argv = ss._server_args(None, 0.0, PORT, ctx=32768)  # base: no steering
    with open(str(out) + ".server.log", "w") as log:
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                cwd=str(common.REPO), env=env)
        try:
            ss._wait_listening(log.name, proc, OPEN_TIMEOUT)
            sumA = [array.array("d", [0.0] * D) for _ in range(nL)]
            sumB = [array.array("d", [0.0] * D) for _ in range(nL)]
            accumulate(A, records, dump, PORT, sumA, nL)
            accumulate(B, records, dump, PORT, sumB, nL)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=30)

    # per-layer direction = unit(mean_A - mean_B); row 0 zero; near-zero layers zero
    rows_out = array.array("f", [0.0] * (nL * D))
    raw_norms = []
    for il in range(nL):
        if il == 0:
            raw_norms.append(0.0); continue
        diff = [sumA[il][k] / len(A) - sumB[il][k] / len(B) for k in range(D)]
        nrm = math.sqrt(sum(x * x for x in diff))
        raw_norms.append(nrm)
        if nrm > ZERO_TOL:
            off = il * D
            for k in range(D):
                rows_out[off + k] = diff[k] / nrm
    out.write_bytes(rows_out.tobytes())
    _write_sidecar(out, A, B, raw_norms, args.ref)
    print(f"wrote {out} ({out.stat().st_size} B); per-layer raw |mean_A-mean_B| "
          f"median {sorted(raw_norms)[nL // 2]:.3f}")
    return 0


def _ref_cosines(out, refs):
    """Per-layer cosine of the produced direction against each `--ref LABEL:PATH`."""
    res = {}
    for spec in refs or []:
        label, _, path = spec.partition(":")
        if not label or not path:
            raise SystemExit(f"--ref expects LABEL:PATH, got {spec!r}")
        res[label] = manifest.layer_cosines(out, path)
    return res


def _write_sidecar(out, A, B, raw_norms, refs=None):
    h = hashlib.sha256(out.read_bytes()).hexdigest()
    cos = _ref_cosines(out, refs)
    for label, c in cos.items():
        print(f"cosine to {label}: median |cos| {c['median_abs']} over {c['layers']} layers")
    (out.with_suffix(".json")).write_text(json.dumps({
        "cosine_to_refs": cos,
        "method": "activation diff-of-means (resist A - open B) at the V4.1 fold, base",
        "site": "v41_attn_input_weighted_fold_post_engram",
        "class_a_resist_idx": A, "class_b_open_idx": B,
        "n_a": len(A), "n_b": len(B),
        "per_layer_raw_norm": [round(x, 4) for x in raw_norms],
        "f32_sha256": h, "f32_shape": [len(raw_norms), D],
        "note": "unit per layer, row 0 zero; near-zero layers zeroed. Judge with 402 before trusting.",
    }, indent=2))


def _self_check():
    # read_last_decision picks the final 40-row block
    import tempfile
    nL = N_LAYERS
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dump.f32"
        a = array.array("f")
        for tok in range(3):               # 3 tokens x nL layers
            for il in range(nL):
                a.extend([float(tok * 100 + il)] * D)
        p.write_bytes(a.tobytes())
        rows = read_last_decision(p)
        assert len(rows) == nL
        assert rows[0][0] == 200.0 and rows[nL - 1][0] == 200.0 + (nL - 1), rows[0][0]
        # --ref: a direction against itself reads |cos| 1 on its nonzero layers, a zero row is skipped
        rows = array.array("f", [0.0] * D + [1.0] + [0.0] * (D - 1) + [1.0] + [0.0] * (D - 1))
        out = Path(d) / "dir.f32"
        out.write_bytes(rows.tobytes())
        c = _ref_cosines(out, [f"self:{out}"])["self"]
        assert c["per_layer"] == [None, 1.0, 1.0] and c["median_abs"] == 1.0, c
    print("extract_floor_direction.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="dir-steering/out/v41-floor-resist.f32")
    ap.add_argument("--b-count", type=int, default=40, help="even-sampled class-B prompts")
    ap.add_argument("--dump", default=None, help="activation dump scratch file")
    ap.add_argument("--ref", action="append", default=[], metavar="LABEL:PATH",
                    help="reference direction file; its per-layer cosine to the result goes in the sidecar (repeatable)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check:
        return _self_check()
    return extract(args)


if __name__ == "__main__":
    sys.exit(main())
