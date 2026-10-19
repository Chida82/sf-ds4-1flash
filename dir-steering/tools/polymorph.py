#!/usr/bin/env python3
"""Polymorphic steering candidates: one unit direction per layer that changes
identity across depth, or sits at equal angle to several sources, or fills the
second (rank-2) slot orthogonally to a reference. Pure Python, no model.

  python3 dir-steering/tools/polymorph.py --self-check
  python3 dir-steering/tools/polymorph.py --mode MODE [--ref REF.f32] [opts] --out OUT.f32 V1.f32 [V2.f32 ...]

Modes (per layer L; inputs are sign-aligned to the first nonzero input, since the
fold `h -= F*d*dot(d,h)` is sign-invariant):
  equiangular  d = unit(sum_i w_i v_i), w = G^-1 1 (G the Gram matrix of the nonzero
               inputs): d has the SAME cosine to every input. The near-parallel
               pair no longer out-votes the lone orthogonal source.
  interleave   d = v_{L mod k}: the direction alternates across depth, so a
               rank-1 slot removes k directions in turn (temporal multiplexing).
               k counts the inputs nonzero at L (3 inputs, one banded: a 3-way
               alternation inside the band, 2-way outside). Input order sets parity.
  interleave-tilt  interleave of the first two inputs, then on layers where the
               third is nonzero, equiangular(that, third): the interleave tilted
               toward the third source inside its band.
  diff         d = unit(v1 - v2): the disagreement axis of a pair. When REF is
               unit(v1+v2) this is exactly orthogonal to REF.
  complement   d = unit(sum of the sign-aligned residuals of every input
               orthogonal to REF): everything the inputs carry beyond REF, as one
               direction. Orthogonal to REF by construction. Needs --ref.
  patchwork    second-slot direction orthogonal to REF that changes identity by
               band: the residual of the LAST input orthogonal to REF where that
               input is nonzero, else diff(v1, v2). Needs --ref and 3 inputs.
  weighted     d = unit(sum_i w_i v_i) with free weights per layer band, inputs unit and
               sign-aligned. --bands "1-9:1,1,0;10-36:.28,.28,.46;37-39:1,1,0" gives w
               (input order) per inclusive layer range; layers in no band use equal
               weights. (1,1) is fused, (1-t,t) the tilt, and G^-1 1 equiangular.
  jitter       control: REF rotated by a random orthogonal direction to cosine
               --cos (default 0.95), seeded. Tells whether a flip comes from the
               geometry or from any perturbation of the same size. Needs --ref.

Writes OUT.f32 (40x5120, row 0 zero, other rows unit or zero: the engine's
validation) and OUT.json: mode, inputs and output sha256, per-layer cosines to
each input and to REF.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fuse_directions import (N_EMBD, N_LAYERS, dot, is_zero, load_f32, norm,  # noqa: E402
                             ortho_residual, sign_align, unit, write_f32)

MODES = ("equiangular", "interleave", "interleave-tilt", "diff", "complement", "patchwork", "jitter", "tilt", "weighted")


def _solve(G, b):
    """Gaussian elimination with partial pivoting for the tiny Gram system."""
    n = len(G)
    M = [row[:] + [b[i]] for i, row in enumerate(G)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            raise ValueError("singular Gram matrix (two inputs are the same direction)")
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def _aligned(rows):
    """Nonzero rows, unit, sign-aligned to the first nonzero one."""
    live = [unit(r) for r in rows if not is_zero(r)]
    return [live[0]] + [sign_align(live[0], r) for r in live[1:]] if live else []


def equiangular(rows):
    v = _aligned(rows)
    if not v:
        return [0.0] * len(rows[0])
    if len(v) == 1:
        return v[0]
    G = [[dot(a, b) for b in v] for a in v]
    w = _solve(G, [1.0] * len(v))
    return unit([sum(wi * vi[j] for wi, vi in zip(w, v)) for j in range(len(v[0]))])


def interleave(rows, L):
    v = _aligned(rows)
    return v[L % len(v)] if v else [0.0] * len(rows[0])


def diff(a, b):
    if is_zero(a) or is_zero(b):
        return [0.0] * len(a)
    au, bu = unit(a), sign_align(a, unit(b))
    d = [x - y for x, y in zip(au, bu)]
    return [0.0] * len(a) if is_zero(d, 1e-6) else unit(d)


def complement(rows, ref):
    if is_zero(ref):
        return [0.0] * len(ref)
    res = [ortho_residual(ref, r) for r in rows if not is_zero(r)]
    v = _aligned([r for r in res if not is_zero(r, 1e-6)])
    if not v:
        return [0.0] * len(ref)
    return unit([sum(vi[j] for vi in v) for j in range(len(ref))])


def patchwork(rows, ref):
    *pair, last = rows
    if not is_zero(last) and not is_zero(ref):
        r = ortho_residual(ref, last)
        if not is_zero(r, 1e-6):
            return unit(r)
    return diff(pair[0], pair[1])


def tilt(a, b, t):
    """unit((1-t)*a + t*b) per layer, sign-aligned. t=0 -> a, t=1 -> b, t=0.5 -> their
    bisector (= fused when a,m are the fuse inputs); t<0 / t>1 extrapolate past an end."""
    if is_zero(a) and is_zero(b):
        return [0.0] * len(a)
    if is_zero(a):
        return unit(b)
    if is_zero(b):
        return unit(a)
    au, bu = unit(a), sign_align(unit(a), unit(b))
    v = [(1.0 - t) * x + t * y for x, y in zip(au, bu)]
    return [0.0] * len(a) if is_zero(v, 1e-6) else unit(v)


def parse_bands(spec):
    """"1-9:1,1,0;10-36:.3,.3,.4" -> {layer: [w, ...]}."""
    out = {}
    for part in filter(None, (p.strip() for p in (spec or "").split(";"))):
        rng_, ws = part.split(":")
        lo, hi = (int(x) for x in rng_.split("-"))
        for L in range(lo, hi + 1):
            out[L] = [float(x) for x in ws.split(",")]
    return out


def weighted(rows, w):
    """unit(sum w_i * v_i) over unit sign-aligned inputs; a zero input drops out with its weight."""
    live = [(i, unit(r)) for i, r in enumerate(rows) if not is_zero(r)]
    if not live:
        return [0.0] * len(rows[0])
    i0, v0 = live[0]
    v = [(i0, v0)] +[(i, sign_align(v0, x)) for i, x in live[1:]]
    ws = w if w else [1.0] * len(rows)
    d = [sum(ws[i] * x[j] for i, x in v) for j in range(len(v0))]
    return [0.0] * len(v0) if is_zero(d, 1e-6) else unit(d)


def jitter(ref, cos, rng):
    if is_zero(ref):
        return [0.0] * len(ref)
    r = unit(ref)
    n = [rng.gauss(0.0, 1.0) for _ in r]
    n = unit(ortho_residual(r, n))
    eps = math.sqrt(1.0 / (cos * cos) - 1.0)
    return unit([x + eps * y for x, y in zip(r, n)])


def build(mode, vecs, ref=None, cos=0.95, seed=1, t=0.5, bands=None):
    n_layers = len(vecs[0]) if vecs else len(ref)
    rng = random.Random(seed)
    out = []
    for L in range(n_layers):
        rows = [v[L] for v in vecs]
        if L == 0:
            d = [0.0] * (len(rows[0]) if rows else len(ref[0]))
        elif mode == "equiangular":
            d = equiangular(rows)
        elif mode == "interleave":
            d = interleave(rows, L)
        elif mode == "interleave-tilt":
            d = equiangular([interleave(rows[:2], L), rows[2]])
        elif mode == "diff":
            d = diff(rows[0], rows[1])
        elif mode == "complement":
            d = complement(rows, ref[L])
        elif mode == "patchwork":
            d = patchwork(rows, ref[L])
        elif mode == "jitter":
            d = jitter(ref[L], cos, rng)
        elif mode == "tilt":
            d = tilt(rows[0], rows[1], t)
        elif mode == "weighted":
            d = weighted(rows, (bands or {}).get(L))
        else:
            raise ValueError(mode)
        out.append(d)
    validate(out)
    return out


def validate(rows):
    """The engine's rule: row 0 zero, every other row unit within 1e-2 or zero."""
    assert is_zero(rows[0]), "row 0 must be zero"
    for L, r in enumerate(rows[1:], 1):
        n = norm(r)
        assert all(math.isfinite(x) for x in r), f"row {L}: non-finite"
        assert n < 1e-9 or abs(n - 1.0) < 1e-2, f"row {L}: norm {n}"


def cosines(rows, other):
    return [None if is_zero(a) or is_zero(b) else round(dot(unit(a), unit(b)), 4)
            for a, b in zip(rows, other)]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- self-check on a synthetic 40x8 case ------------------------------------

def _self_check():
    rng = random.Random(7)
    n, D = 40, 8

    def rand_unit():
        return unit([rng.gauss(0, 1) for _ in range(D)])

    zero = [0.0] * D
    a = [zero] + [rand_unit() for _ in range(n - 1)]
    m = [zero] + [unit([x + 0.3 * y for x, y in zip(a[L], rand_unit())]) for L in range(1, n)]
    d = [zero] + [zero if L < 10 or L > 36 else rand_unit() for L in range(1, n)]
    fused = [zero] + [unit([x + y for x, y in zip(a[L], m[L])]) for L in range(1, n)]

    eq = build("equiangular", [a, m, d])
    for L in range(1, n):
        cs = [abs(dot(eq[L], v[L])) for v in (a, m, d) if not is_zero(v[L])]
        assert max(cs) - min(cs) < 1e-9, (L, cs)
    il = build("interleave", [a, m])
    assert abs(abs(dot(il[1], m[1])) - 1) < 1e-9 and abs(dot(il[2], a[2]) - 1) < 1e-9  # L mod 2
    df = build("diff", [a, m], ref=fused)
    assert all(abs(dot(df[L], fused[L])) < 1e-9 for L in range(1, n)), "diff not orthogonal to unit(a+m)"
    cp = build("complement", [a, m, d], ref=fused)
    assert all(abs(dot(cp[L], fused[L])) < 1e-9 for L in range(1, n))
    pw = build("patchwork", [a, m, d], ref=fused)
    assert all(abs(dot(pw[L], fused[L])) < 1e-9 for L in range(1, n))
    assert abs(dot(pw[5], df[5]) - 1) < 1e-9 and abs(dot(pw[20], df[20])) < 0.99, \
        "patchwork must switch identity by band"
    jt = build("jitter", [], ref=fused, cos=0.9, seed=3)
    assert all(abs(dot(jt[L], fused[L]) - 0.9) < 1e-9 for L in range(1, n))
    # a layer where only one input is nonzero: equiangular returns that input
    one = build("equiangular", [a, d])
    assert abs(dot(one[5], a[5]) - 1) < 1e-9
    it = build("interleave-tilt", [a, m, d])
    assert abs(dot(it[5], il[5]) - 1) < 1e-9                       # outside the band: interleave
    cs = (abs(dot(it[20], il[20])), abs(dot(it[20], d[20])))
    assert abs(cs[0] - cs[1]) < 1e-9 and cs[0] < 1 - 1e-6, cs        # inside: equal angle to both
    i3 = build("interleave", [a, m, d])
    same = lambda x, y: abs(abs(dot(x, y)) - 1) < 1e-9  # noqa: E731
    assert same(i3[5], m[5])                                        # 2-way outside the band
    assert same(i3[21], a[21]) and same(i3[22], m[22]) and same(i3[23], d[23])  # 3-way inside
    # degenerate pair: diff of a vector with itself is a zero (masked) row
    assert is_zero(build("diff", [a, a])[3])
    # tilt: t=0 -> a, t=1 -> m, t=0.5 -> fused (the bisector); endpoints exact
    t0 = build("tilt", [a, m], t=0.0)
    t1 = build("tilt", [a, m], t=1.0)
    th = build("tilt", [a, m], t=0.5)
    assert all(abs(abs(dot(t0[L], a[L])) - 1) < 1e-9 for L in range(1, n)), "tilt t=0 != a"
    assert all(abs(abs(dot(t1[L], m[L])) - 1) < 1e-9 for L in range(1, n)), "tilt t=1 != m"
    assert all(abs(dot(th[L], fused[L]) - 1) < 1e-9 for L in range(1, n)), "tilt t=0.5 != fused"
    # weighted: (1,1,0) is fused, (1-t,t,0) is tilt, the equiangular weights give equiangular,
    # a banded spec changes only its band
    wf = build("weighted", [a, m, d], bands=parse_bands("1-39:1,1,0"))
    assert all(abs(dot(wf[L], fused[L]) - 1) < 1e-9 for L in range(1, n)), "weighted(1,1,0) != fused"
    wt = build("weighted", [a, m], bands=parse_bands("1-39:.25,.75"))
    tt = build("tilt", [a, m], t=0.75)
    assert all(abs(dot(wt[L], tt[L]) - 1) < 1e-9 for L in range(1, n)), "weighted != tilt"
    L = 20
    v = _aligned([a[L], m[L], d[L]])
    w = _solve([[dot(x, y) for y in v] for x in v], [1.0] * 3)
    we = build("weighted", [a, m, d], bands=parse_bands(f"20-20:{w[0]},{w[1]},{w[2]}"))
    assert abs(dot(we[L], eq[L]) - 1) < 1e-9, "weighted != equiangular"
    wb = build("weighted", [a, m, d], bands=parse_bands("10-36:1,1,1"))
    assert abs(dot(wb[5], fused[5]) - 1) < 1e-9, "unlisted layer must be equal weights"
    print("ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument("--ref", help="reference .f32 (complement/patchwork/jitter; diff/equiangular report cosines to it)")
    ap.add_argument("--cos", type=float, default=0.95, help="jitter: cosine to REF")
    ap.add_argument("--t", type=float, default=0.5, help="tilt: 0=first vector, 1=second, 0.5=bisector")
    ap.add_argument("--bands", help="weighted: 'lo-hi:w1,w2,..;lo-hi:...' per inclusive layer range")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("vectors", nargs="*")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if not a.mode or not a.out:
        ap.error("--mode and --out are required")
    need = {"diff": 2, "patchwork": 3, "interleave-tilt": 3, "tilt": 2}.get(a.mode)
    if need and len(a.vectors) != need:
        ap.error(f"{a.mode} takes exactly {need} vectors")
    if a.mode in ("complement", "patchwork", "jitter") and not a.ref:
        ap.error(f"{a.mode} needs --ref")
    vecs = [load_f32(p) for p in a.vectors]
    ref = load_f32(a.ref) if a.ref else None
    rows = build(a.mode, vecs, ref=ref, cos=a.cos, seed=a.seed, t=a.t, bands=parse_bands(a.bands))
    write_f32(a.out, rows)
    side = {
        "mode": a.mode, "seed": a.seed if a.mode == "jitter" else None,
        "t": a.t if a.mode == "tilt" else None,
        "bands": a.bands if a.mode == "weighted" else None,
        "inputs": [{"path": p, "sha256": sha256(p)} for p in a.vectors],
        "ref": {"path": a.ref, "sha256": sha256(a.ref)} if a.ref else None,
        "output": {"path": a.out, "sha256": sha256(a.out)},
        "cos_to_inputs": {Path(p).name: cosines(rows, v) for p, v in zip(a.vectors, vecs)},
        "cos_to_ref": cosines(rows, ref) if ref else None,
        "zero_layers": [L for L, r in enumerate(rows) if is_zero(r)],
    }
    Path(a.out).with_suffix(".json").write_text(json.dumps(side, indent=1) + "\n")
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None  # noqa: E731
    print(f"wrote {a.out} sha256 {side['output']['sha256'][:12]} zero layers {side['zero_layers']}")
    for k, cs in side["cos_to_inputs"].items():
        print(f"  median |cos| to {k}: {med([abs(c) for c in cs if c is not None])}")
    if ref:
        print(f"  median |cos| to ref: {med([abs(c) for c in side['cos_to_ref'] if c is not None])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
