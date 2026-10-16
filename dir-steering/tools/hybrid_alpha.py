#!/usr/bin/env python3
"""Generate hybrid(α) = unit(msuiche + α·abl_perp) per layer.

abl_perp is the orthogonal residual of abliteration vs msuiche — the part of
abliteration that msuiche does NOT already remove. Mixing it in rotates the
single removal direction toward abliteration's coverage without doubling the
shared component (which is what breaks rank-2 and naive sums).

  python3 dir-steering/tools/hybrid_alpha.py --self-check
  python3 dir-steering/tools/hybrid_alpha.py --alphas 0.1,0.3,0.5,0.7,1.0
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

N_LAYERS = 40
D = 5120


def load_f32(path):
    data = Path(path).read_bytes()
    exp = N_LAYERS * D * 4
    if len(data) != exp:
        raise SystemExit(f"{path}: {len(data)} B, expected {exp}")
    flat = struct.unpack(f"<{N_LAYERS * D}f", data)
    return [list(flat[L * D:(L + 1) * D]) for L in range(N_LAYERS)]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return [x / n for x in a] if n > 1e-12 else list(a)


def hybrid(msu, perp, alpha):
    out = []
    for L in range(len(msu)):
        m, p = msu[L], perp[L]
        if norm(m) < 1e-12:
            out.append([0.0] * len(m))
            continue
        v = [m[k] + alpha * p[k] for k in range(len(m))]
        out.append(unit(v))
    return out


def write_f32(path, rows):
    flat = [x for row in rows for x in row]
    Path(path).write_bytes(struct.pack(f"<{len(flat)}f", *flat))


def cos_per_layer(a, b):
    cs = []
    for L in range(N_LAYERS):
        na, nb = norm(a[L]), norm(b[L])
        if na < 1e-12 or nb < 1e-12:
            cs.append(None)
        else:
            cs.append(dot(a[L], b[L]) / (na * nb))
    return cs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--msuiche", default="dir-steering/vectors/v41-msuiche.f32")
    ap.add_argument("--perp", default="dir-steering/out/v41-fusedmsuiche-abl-ortho.f32",
                    help="abl_perp (orthogonal residual of abliteration vs msuiche)")
    ap.add_argument("--alphas", default="0.1,0.3,0.5,0.7,1.0",
                    help="comma-separated α values")
    ap.add_argument("--out", default="dir-steering/out", help="output directory")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)

    if args.self_check:
        a = unit([1.0, 0.0, 0.0, 0, 0, 0, 0, 0])
        p = unit([0.0, 1.0, 0.0, 0, 0, 0, 0, 0])
        M = [a]; P = [p]
        h = hybrid(M, P, 0.5)[0]
        assert abs(norm(h) - 1.0) < 1e-9
        expected_cos_a = 1.0 / math.sqrt(1 + 0.25)
        assert abs(dot(h, a) - expected_cos_a) < 1e-6, f"{dot(h, a)} vs {expected_cos_a}"
        assert abs(dot(h, p) - 0.5 / math.sqrt(1.25)) < 1e-6
        h0 = hybrid(M, P, 0.0)[0]
        assert abs(dot(h0, a) - 1.0) < 1e-9, "α=0 should be pure msuiche"
        print("hybrid_alpha.py self-check: OK")
        return 0

    msu = load_f32(args.msuiche)
    perp = load_f32(args.perp)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    alphas = [float(x) for x in args.alphas.split(",")]
    for alpha in alphas:
        tag = f"{alpha:.1f}".replace(".", "")
        rows = hybrid(msu, perp, alpha)
        f32_path = outdir / f"v41-hybrid-a{tag}.f32"
        write_f32(f32_path, rows)
        data = f32_path.read_bytes()
        cos_msu = cos_per_layer(rows, msu)
        valid = [c for c in cos_msu if c is not None]
        med = sorted(valid)[len(valid) // 2] if valid else 0
        sidecar = {
            "method": f"hybrid(α={alpha}): unit(msuiche + {alpha}·abl_perp)",
            "alpha": alpha,
            "cos_vs_msuiche_median": round(med, 4),
            "cos_vs_msuiche_per_layer": [None if c is None else round(c, 4) for c in cos_msu],
            "sources": {"msuiche": str(args.msuiche), "abl_perp": str(args.perp)},
            "f32_sha256": hashlib.sha256(data).hexdigest(),
            "f32_shape": [N_LAYERS, D],
        }
        (f32_path.with_suffix(".json")).write_text(json.dumps(sidecar, indent=2))
        print(f"α={alpha:.1f}  cos(hybrid,msuiche) median={med:.4f}  → {f32_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
