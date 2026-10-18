"""Zero chosen layer rows of a steering matrix (409 arm 4, per-layer allocation).

  python3 dir-steering/tools/mask_layers.py --in A.f32 --out B.f32 --zero-layers 9-39
  python3 dir-steering/tools/mask_layers.py --in abl.f32 --out B.f32 \\
      --zero-where-cos-above 0.4 --against msuiche.f32
  python3 dir-steering/tools/mask_layers.py --self-check

A zeroed row is a valid mask for the engine (unit or all-zero rows). Writes the
output and a `.json` sidecar: source and output sha256, the rule, and the zeroed
layers (with their |cos| when the rule is the cosine one).
"""
import argparse
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

from fuse_directions import N_EMBD, N_LAYERS, load_f32, per_layer_cosine, unit, write_f32


def parse_layers(spec):
    """'9-39,0' -> sorted set of layer indices."""
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    bad = [L for L in out if not 0 <= L < N_LAYERS]
    if bad:
        raise SystemExit(f"layers out of range 0..{N_LAYERS - 1}: {bad}")
    return sorted(out)


def mask(rows, zero_layers=None, cos_above=None, against=None):
    """Return (masked rows, zeroed layers, {layer: |cos|} for the cosine rule)."""
    if zero_layers is not None:
        zeroed, cos = list(zero_layers), {}
    else:
        c = per_layer_cosine(rows, against, 0)
        zeroed = [L for L, x in enumerate(c) if x is not None and abs(x) > cos_above]
        cos = {L: round(abs(c[L]), 4) for L in zeroed}
    out = [[0.0] * len(r) if L in zeroed else r for L, r in enumerate(rows)]
    return out, zeroed, cos


def run(args):
    rows = load_f32(args.inp)
    if args.zero_layers:
        out, zeroed, cos = mask(rows, zero_layers=parse_layers(args.zero_layers))
        rule = f"zero-layers {args.zero_layers}"
    else:
        if not args.against:
            raise SystemExit("--zero-where-cos-above needs --against REF.f32")
        out, zeroed, cos = mask(rows, cos_above=args.zero_where_cos_above, against=load_f32(args.against))
        rule = f"zero-where-cos-above {args.zero_where_cos_above} against {args.against}"
    data = write_f32(args.out, out)
    Path(args.out).with_suffix(".json").write_text(json.dumps({
        "source": args.inp,
        "source_sha256": hashlib.sha256(Path(args.inp).read_bytes()).hexdigest(),
        "rule": rule,
        "zeroed_layers": zeroed,
        "zeroed_cos": cos,
        "f32_sha256": hashlib.sha256(data).hexdigest(),
    }, indent=2))
    print(f"{args.out}: zeroed {len(zeroed)} layers {zeroed}")
    return 0


def _self_check():
    rng = random.Random(409)
    rows = [[0.0] * N_EMBD] + [unit([rng.gauss(0, 1) for _ in range(N_EMBD)]) for _ in range(N_LAYERS - 1)]
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "a.f32", Path(d) / "b.f32"
        write_f32(src, rows)
        run(argparse.Namespace(inp=str(src), out=str(dst), zero_layers="9-39",
                               zero_where_cos_above=None, against=None))
        a, b = src.read_bytes(), dst.read_bytes()
        row = N_EMBD * 4
        assert all(x == 0 for x in b[9 * row:]), "rows 9-39 not zero"
        assert a[:9 * row] == b[:9 * row], "rows 0-8 changed"
        # cosine rule: plant |cos| ~0.8 (one with a flipped sign) on layers 3 and 20
        ref = [list(r) for r in rows]
        for L, sgn in ((3, 1.0), (20, -1.0)):
            perp = unit([rng.gauss(0, 1) for _ in range(N_EMBD)])
            ref[L] = unit([sgn * (0.8 * x + 0.6 * y) for x, y in zip(rows[L], perp)])
        for L in range(1, N_LAYERS):
            if L not in (3, 20):
                ref[L] = unit([rng.gauss(0, 1) for _ in range(N_EMBD)])
        _, zeroed, cos = mask(rows, cos_above=0.4, against=ref)
        assert zeroed == [3, 20], zeroed
        assert all(abs(c - 0.8) < 0.05 for c in cos.values()), cos
    assert parse_layers("9-11,0") == [0, 9, 10, 11]
    print("ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--out")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--zero-layers", help="ranges and singles, e.g. 9-39,0")
    g.add_argument("--zero-where-cos-above", type=float)
    ap.add_argument("--against", help="reference matrix for the cosine rule")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if not a.inp or not a.out or (a.zero_layers is None and a.zero_where_cos_above is None):
        ap.error("--in, --out and one of --zero-layers / --zero-where-cos-above are required")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
