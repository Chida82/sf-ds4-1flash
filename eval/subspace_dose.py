#!/usr/bin/env python3
"""Compliance direction with a per-layer dose for the probe-driven slot 2.

The refused prompts carry u1 (refusal) and lack d2 (the refused-minus-complied
direction orthogonal to u1: refused read ~0 along it, complied are displaced).
The engine's probe-dosed slot computes  x -= G * row_l * dot(u1_l, x).  With
G = -1 and  row_l = (mu_com_d2[l] - mu_ref_d2[l]) / mu_ref_u1[l] * d2_l  a row
carrying the typical refused component along u1 is moved exactly to the complied
displacement along d2; a benign row (dot ~ 0) is left alone.

  python3 eval/subspace_dose.py --capture eval/out-subspace-1017/capture \
      --u1 dir-steering/out/v41-sub1017-u1.f32 --d2 dir-steering/out/v41-sub1017-d2.f32 \
      --out dir-steering/out/v41-sub1017-d2dose
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subspace_analysis as sa  # noqa: E402

L, D = 40, 5120


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--u1", required=True)
    ap.add_argument("--d2", required=True)
    ap.add_argument("--out", required=True, help="prefix: writes <out>.f32 and <out>.json")
    ap.add_argument("--position", default="rows")
    ap.add_argument("--min-probe", type=float, default=5.0,
                    help="zero the row where |mu_ref.u1| is below this (no probe signal: the dose would explode)")
    a = ap.parse_args(argv)

    ids, X, recs = sa.load_capture(a.capture, a.position)
    ref = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is True])
    com = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is False])
    u1 = np.fromfile(a.u1, dtype=np.float32).reshape(L, D)
    d2 = np.fromfile(a.d2, dtype=np.float32).reshape(L, D)
    out = np.zeros((L, D), np.float32)
    lines = ["| layer | mu_ref.u1 | mu_ref.d2 | mu_com.d2 | dose | row norm |", "|---|---|---|---|---|---|"]
    for l in range(1, L):
        if not u1[l].any() or not d2[l].any():
            continue
        r_u1 = float((X[ref, l] @ u1[l]).mean())
        r_d2 = float((X[ref, l] @ d2[l]).mean())
        c_d2 = float((X[com, l] @ d2[l]).mean())
        dose = (c_d2 - r_d2) / r_u1 if abs(r_u1) >= a.min_probe else 0.0
        out[l] = dose * d2[l]
        lines.append(f"| {l} | {r_u1:.1f} | {r_d2:.1f} | {c_d2:.1f} | {dose:.3f} | {abs(dose):.3f} |")
    out.tofile(a.out + ".f32")
    sha = hashlib.sha256(Path(a.out + ".f32").read_bytes()).hexdigest()
    Path(a.out + ".json").write_text(json.dumps({
        "source": f"d2 ({a.d2}) scaled per layer by (mu_com.d2 - mu_ref.d2)/mu_ref.u1 from {a.capture} ({a.position}); "
                  "probe-dosed slot 2 with --dir-steering-probe-2 u1 and --dir-steering-residual-2 -1 moves a typical "
                  "refused row to the complied displacement; rows are NOT unit (dose in the norm)",
        "direction": "d2dose", "probe": a.u1, "sha256": sha, "table": lines}, indent=1) + "\n")
    print("\n".join(lines))
    print(f"wrote {a.out}.f32 sha256 {sha[:12]}")


if __name__ == "__main__":
    main()
