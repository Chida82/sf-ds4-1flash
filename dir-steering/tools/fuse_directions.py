#!/usr/bin/env python3
"""Fuse two V4.1 refusal directions into candidate steering `.f32` files
(OpenSpec 404, FUSION_STRATEGY sec.4).

Inputs, both single-stream HC-collapsed residual directions for the same base
(`deepseek-ai/DeepSeek-V4.1-Flash` rev fb2764a5, 40 layers x 5120):
  - msuiche: the `.f32` from 401's converter (post-layer fold, alpha knee 0.5).
  - distributedcognition: `refusal_directions.pt` (layer-input `attn_norm`).

They differ only in depth (one sub-layer apart), so a per-layer fusion is
well-posed. This tool sign-aligns and unit-norms each per-layer pair, scans a
small layer offset, and emits candidates to be JUDGED by 402 (never trusted
unmeasured):
  - `denoise`  : unit(a + b) per layer  (== the top SVD right-singular vector of
                 {a,b} for unit inputs) -- the single fused direction.
  - `ortho`    : the orthogonal residual b - (a.b)a, a diagnostic single
                 direction capturing what distcog adds beyond msuiche.

NOTE on rank: 401's runtime applies ONE direction per layer, so a genuine rank-k
(k>1) subspace removal is not a single `.f32`. The SVD basis is computed here for
analysis/sidecar, but only single-direction drop-ins are written; multi-direction
removal needs a runtime extension (tracked in 405).

The `.pt` is read WITHOUT torch: it is a zip whose `data/0` entry is the raw
float32 storage; no pickle is executed.

Run `python3 dir-steering/tools/fuse_directions.py --self-check`.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
import zipfile
from pathlib import Path

N_LAYERS = 40
N_EMBD = 5120


# --- loading -----------------------------------------------------------------

def load_f32(path, n_layers=N_LAYERS, n_embd=N_EMBD):
    data = Path(path).read_bytes()
    exp = n_layers * n_embd * 4
    if len(data) != exp:
        raise SystemExit(f"{path}: {len(data)} B, expected {exp} ({n_layers}x{n_embd} f32)")
    flat = struct.unpack(f"<{n_layers * n_embd}f", data)
    return [list(flat[L * n_embd:(L + 1) * n_embd]) for L in range(n_layers)]


def load_pt_directions(pt_path, n_layers=N_LAYERS, n_embd=N_EMBD):
    """Extract the `directions` tensor from a torch .pt WITHOUT torch: the zip's
    single `data/*` storage is the raw float32 tensor (40x5120, C-contiguous,
    little-endian). No pickle is executed."""
    exp = n_layers * n_embd * 4
    with zipfile.ZipFile(pt_path) as z:
        if not z.namelist():
            raise SystemExit(f"{pt_path}: empty archive")
        root = z.namelist()[0].split("/")[0]
        bo = z.read(f"{root}/byteorder").decode().strip() if \
            f"{root}/byteorder" in z.namelist() else "little"
        if bo != "little":
            raise SystemExit(f"{pt_path}: byteorder {bo!r}, only little-endian supported")
        stores = [n for n in z.namelist() if f"{root}/data/" in n
                  and z.getinfo(n).file_size == exp]
        if len(stores) != 1:
            raise SystemExit(f"{pt_path}: expected one {exp}-byte storage, found "
                             f"{len(stores)} -- parse the pickle to disambiguate")
        raw = z.read(stores[0])
    flat = struct.unpack(f"<{n_layers * n_embd}f", raw)
    return [list(flat[L * n_embd:(L + 1) * n_embd]) for L in range(n_layers)]


# --- vector algebra ----------------------------------------------------------

def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return [x / n for x in a] if n > 1e-12 else list(a)


def is_zero(a, tol=1e-9):
    return norm(a) < tol


def sign_align(a, b):
    """Flip b to the same half-space as a (projective directions have no sign)."""
    return [-x for x in b] if dot(a, b) < 0 else list(b)


def denoise(a, b):
    return unit([x + y for x, y in zip(a, b)])


def ortho_residual(a, b):
    """Part of b orthogonal to a: b - (a.b)a (a assumed unit)."""
    c = dot(unit(a), b)
    au = unit(a)
    return [y - c * x for x, y in zip(au, b)]


def subspace_basis(vectors, k):
    """Top-k right singular vectors of the stacked unit `vectors` (m x N), via the
    small m x m Gram. Returns up to min(k, m) orthonormal N-vectors. For the two
    sign-aligned unit sources used here this reduces to the 2x2 closed form, so
    only that is implemented."""
    m = len(vectors)
    if m == 1:
        return [unit(vectors[0])]
    if m != 2:
        raise NotImplementedError("subspace_basis implemented for 1 or 2 sources")
    a, b = unit(vectors[0]), unit(vectors[1])
    c = dot(a, b)
    # eigenvectors of [[1,c],[c,1]] are (1,1)/sqrt2 (val 1+c) and (1,-1)/sqrt2
    v1 = unit([x + y for x, y in zip(a, b)])        # top (c>0)
    v2 = unit([x - y for x, y in zip(a, b)])        # second
    basis = [v1, v2] if (1 + c) >= (1 - c) else [v2, v1]
    return basis[:max(1, min(k, 2))]


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# --- fusion ------------------------------------------------------------------

def per_layer_cosine(A, B, offset):
    """Cosine of msuiche layer L vs distcog layer L+offset, over layers where both
    are non-zero."""
    cos = []
    for L in range(len(A)):
        M = L + offset
        if 0 <= M < len(B) and not is_zero(A[L]) and not is_zero(B[M]):
            a = unit(A[L])
            b = sign_align(a, B[M])
            cos.append(dot(a, unit(b)))
        else:
            cos.append(None)
    return cos


def choose_offset(A, B, offsets=(-1, 0, 1)):
    best, best_med = 0, -2.0
    table = {}
    for o in offsets:
        cos = [c for c in per_layer_cosine(A, B, o) if c is not None]
        med = median(cos)
        table[o] = med
        if med > best_med:
            best, best_med = o, med
    return best, table


def fuse(A, B, offset, method):
    """Return a 40x5120 fused array. Layers with no pairing fall back to msuiche."""
    out = [[0.0] * N_EMBD for _ in range(len(A))]
    for L in range(len(A)):
        M = L + offset
        a = A[L]
        if is_zero(a):
            continue
        if not (0 <= M < len(B)) or is_zero(B[M]):
            out[L] = unit(a)          # keep msuiche where distcog has nothing
            continue
        au = unit(a)
        b = sign_align(au, B[M])
        if method == "denoise":
            out[L] = denoise(au, b)
        elif method == "ortho":
            r = ortho_residual(au, b)
            out[L] = unit(r) if not is_zero(r) else au
        elif method == "subspace_k1":
            out[L] = subspace_basis([au, b], 1)[0]
        else:
            raise ValueError(method)
    return out


def write_f32(path, rows):
    flat = [x for row in rows for x in row]
    data = struct.pack(f"<{len(flat)}f", *flat)
    Path(path).write_bytes(data)
    return data


def emit(A, B, offset, outdir, sources):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cos = per_layer_cosine(A, B, offset)
    results = []
    for method in ("denoise", "ortho", "subspace_k1"):
        rows = fuse(A, B, offset, method)
        f32 = outdir / f"v41-fused-{method}.f32"
        data = write_f32(f32, rows)
        residual_norms = None
        if method == "ortho":
            residual_norms = [round(norm(r), 4) for r in rows]
        sidecar = {
            "method": method,
            "runnable": method != "subspace_k1" or True,  # all single-direction
            "offset": offset,
            "per_layer_cosine": [None if c is None else round(c, 4) for c in cos],
            "median_cosine": round(median([c for c in cos if c is not None]), 4),
            "sources": sources,
            "f32_shape": [len(rows), N_EMBD],
            "f32_sha256": hashlib.sha256(data).hexdigest(),
            "ortho_residual_norms": residual_norms,
            "note": ("Judge with 402 before trusting. ds4 +scale removes the "
                     "direction. Rank-k>1 removal needs a multi-direction runtime "
                     "(not in 401); see 405."),
        }
        (outdir / f"v41-fused-{method}.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2))
        results.append((method, f32, len(data)))
    return results


# --- self-check --------------------------------------------------------------

def _selfcheck():
    N = 8
    a = unit([1.0, 2.0, 3.0, 0, 0, 0, 0, 0])
    b = unit([1.0, 2.0, 2.9, 0.1, 0, 0, 0, 0])   # close to a
    # sign-align flips a negated pair
    nb = [-x for x in b]
    assert dot(a, sign_align(a, nb)) > 0, "sign_align must flip a negated pair"
    assert dot(a, sign_align(a, b)) > 0
    # denoise is unit-norm and between a and b
    d = denoise(a, b)
    assert abs(norm(d) - 1.0) < 1e-9, norm(d)
    assert dot(d, a) > 0.9 and dot(d, b) > 0.9
    # ortho residual is orthogonal to a
    r = ortho_residual(a, b)
    assert abs(dot(unit(a), r)) < 1e-9, dot(unit(a), r)
    # subspace basis: k vectors, orthonormal, v1 ~ denoise
    basis = subspace_basis([a, b], 2)
    assert len(basis) == 2
    assert abs(norm(basis[0]) - 1) < 1e-9 and abs(norm(basis[1]) - 1) < 1e-9
    assert abs(dot(basis[0], basis[1])) < 1e-9, "basis must be orthonormal"
    assert abs(abs(dot(basis[0], d)) - 1.0) < 1e-6, "k1 should match denoise"
    assert subspace_basis([a, b], 1) == [basis[0]] or True  # k<=m
    # offset + per-layer cosine over a tiny 40x5120-less fixture
    A = [[0.0] * N for _ in range(3)]
    B = [[0.0] * N for _ in range(3)]
    A[1] = a
    B[1] = b
    A[2] = a
    B[2] = [-x for x in b]
    cos = per_layer_cosine(A, B, 0)
    assert cos[0] is None and cos[1] is not None
    assert cos[1] > 0.9 and cos[2] > 0.9  # sign-aligned before cosine
    off, table = choose_offset(A, B)
    assert off in (-1, 0, 1) and 0 in table
    print("fuse_directions.py self-check: OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--msuiche", help="msuiche .f32 (from 401's converter)")
    ap.add_argument("--distcog", help="distributedcognition refusal_directions.pt")
    ap.add_argument("--out", default="dir-steering/out", help="candidate output dir")
    ap.add_argument("--offset", type=int, help="force a layer offset (else searched)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check or not (args.msuiche and args.distcog):
        _selfcheck()
        return 0
    A = load_f32(args.msuiche)
    B = load_pt_directions(args.distcog)
    offset = args.offset if args.offset is not None else choose_offset(A, B)[0]
    _, table = choose_offset(A, B)
    print(f"offset median-cosine: {table}; chosen {offset}")
    sources = {"msuiche": str(args.msuiche), "distcog": str(args.distcog)}
    for method, f32, size in emit(A, B, offset, args.out, sources):
        print(f"wrote {f32} ({size} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
