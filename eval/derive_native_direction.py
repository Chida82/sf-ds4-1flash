"""Native refusal direction and principal components from a base fold capture (409 D3).

  python3 eval/derive_native_direction.py --capture eval/out/capture/base --out-dir dir-steering/out --k 2
  python3 eval/derive_native_direction.py --self-check

`v41-native-refusal.f32`: per layer unit(mean(A u B) - mean(benign)), row 0 zero, rows
whose raw norm is under 1e-6 zero. `v41-native-pc1..pcK.f32`: per layer the top
principal components of the harmful rows centred on the benign mean (h_i - mean(benign)),
from the n x n Gram matrix by power iteration with deflation, Gram-Schmidt per layer so
pc1..pcK are orthonormal, sign so that dot(pc_j, native) >= 0. Each output gets a
`.json` sidecar. Pure Python, deterministic (fixed start vector).
"""
import argparse
import hashlib
import json
import math
import operator
import random
import sys
import tempfile
from pathlib import Path

import analyze_fold as af

D, N_LAYERS = af.D, af.N_LAYERS
ZERO_TOL = 1e-6
POWER_STEPS, POWER_TOL = 200, 1e-9


def mean_rows(rows):
    acc = [0.0] * len(rows[0])
    for r in rows:
        acc = list(map(operator.add, acc, r))
    return [v / len(rows) for v in acc]


def unit_or_zero(v):
    n = af.norm(v)
    return ([x / n for x in v], n) if n >= ZERO_TOL else ([0.0] * len(v), n)


def top_components(X, k):
    """Top-k principal directions of the rows of X (already centred) via the n x n Gram
    matrix: power iteration with deflation on G = X X^T, then v = X^T u / |X^T u|.
    Returns (directions, eigenvalues, trace)."""
    n = len(X)
    G = [[af.dot(X[i], X[j]) for j in range(n)] for i in range(n)]
    trace = sum(G[i][i] for i in range(n))
    dirs, eigs = [], []
    for _ in range(k):
        u = [1.0 / math.sqrt(n)] * n
        lam = 0.0
        for _ in range(POWER_STEPS):
            w = [af.dot(G[i], u) for i in range(n)]
            nw = af.norm(w)
            if nw == 0.0:
                break
            w = [x / nw for x in w]
            done = af.norm([a - b for a, b in zip(w, u)]) < POWER_TOL
            u, lam = w, nw
            if done:
                break
        G = [[G[i][j] - lam * u[i] * u[j] for j in range(n)] for i in range(n)]
        v = [0.0] * len(X[0])
        for i in range(n):
            if u[i]:
                v = [a + u[i] * b for a, b in zip(v, X[i])]
        dirs.append(v)
        eigs.append(lam)
    return dirs, eigs, trace


def derive(prompts, k):
    harm = [p for p in prompts if p["class"] in ("A", "B")]
    benign = [p for p in prompts if p["class"] == "benign"]
    native = [[0.0] * D for _ in range(N_LAYERS)]
    pcs = [[[0.0] * D for _ in range(N_LAYERS)] for _ in range(k)]
    raw_norm, shares = [0.0] * N_LAYERS, [[0.0] * N_LAYERS for _ in range(k)]
    for L in range(1, N_LAYERS):
        mb = mean_rows([p["rows"][L] for p in benign])
        mh = mean_rows([p["rows"][L] for p in harm])
        native[L], raw_norm[L] = unit_or_zero([a - b for a, b in zip(mh, mb)])
        X = [[a - b for a, b in zip(p["rows"][L], mb)] for p in harm]
        dirs, eigs, trace = top_components(X, k)
        ortho = af.gram_schmidt(dirs)
        for j, v in enumerate(ortho):
            if v is None:
                continue
            if af.dot(v, native[L]) < 0:
                v = [-x for x in v]
            pcs[j][L] = v
            shares[j][L] = eigs[j] / trace if trace else 0.0
    return native, raw_norm, pcs, shares


def write(path, rows):
    import array
    a = array.array("f", [x for r in rows for x in r])
    data = a.tobytes()
    Path(path).write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def run(args):
    m, prompts = af.load_capture(args.capture)
    native, raw_norm, pcs, shares = derive(prompts, args.k)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    refs = {k: af.load_rows(af.REFS[k]) for k in ("msuiche", "audreyt", "floor_resist")}
    n = {c: sum(p["class"] == c for p in prompts) for c in ("A", "B", "benign")}

    def cos_to_refs(rows):
        return {k: [af.cos_rows(rows[L], refs[k][L]) for L in range(N_LAYERS)] for k in refs}

    base = {"capture": str(args.capture), "capture_run_id": m.get("run_id"), "class_sizes": n,
            "site": "v41_attn_input_weighted_fold_post_engram"}
    path = out / "v41-native-refusal.f32"
    sha = write(path, native)
    path.with_suffix(".json").write_text(json.dumps(dict(base, method="unit(mean(A u B) - mean(benign))",
        per_layer_raw_norm=[round(x, 4) for x in raw_norm], cos=cos_to_refs(native), f32_sha256=sha),
        indent=1))
    print(f"wrote {path}")
    for j in range(args.k):
        path = out / f"v41-native-pc{j + 1}.f32"
        sha = write(path, pcs[j])
        path.with_suffix(".json").write_text(json.dumps(dict(base,
            method=f"principal component {j + 1} of h - mean(benign) over A u B (Gram, power iteration)",
            explained_variance_share=[round(x, 4) for x in shares[j]],
            cos=cos_to_refs(pcs[j]), f32_sha256=sha), indent=1))
        print(f"wrote {path}")
    return 0


def _self_check():
    rng = random.Random(409)
    dim, n = 256, 30

    def unit(v):
        nv = af.norm(v)
        return [x / nv for x in v]
    planted = unit([rng.gauss(0, 1) for _ in range(dim)])
    spread = af.gram_schmidt([planted, [rng.gauss(0, 1) for _ in range(dim)]])[1]
    benign = [[rng.gauss(0, 0.1) for _ in range(dim)] for _ in range(n)]
    # harmful = benign-like noise + 8 along `planted` (with a +-4 spread) + +-2 along `spread`
    harm = [[0.1 * rng.gauss(0, 1) + (8 + 4 * rng.choice((-1, 1))) * p + 2 * rng.choice((-1, 1)) * s
             for p, s in zip(planted, spread)] for _ in range(n)]
    mb = mean_rows(benign)
    nat, _ = unit_or_zero([a - b for a, b in zip(mean_rows(harm), mb)])
    assert af.dot(nat, planted) >= 0.99, af.dot(nat, planted)
    X = [[a - b for a, b in zip(h, mb)] for h in harm]
    dirs, eigs, _ = top_components(X, 2)
    pc1, pc2 = af.gram_schmidt(dirs)
    assert abs(af.dot(pc1, planted)) >= 0.99, af.dot(pc1, planted)
    assert abs(af.dot(pc1, pc2)) < 1e-6
    assert eigs[0] >= eigs[1] > 0
    dirs2, _, _ = top_components(X, 2)
    assert dirs == dirs2, "not deterministic"
    with tempfile.TemporaryDirectory() as d:
        rows = [[0.0] * 4, [0.6, 0.8, 0.0, 0.0]]
        assert write(Path(d) / "a", rows) == write(Path(d) / "b", rows)
    print("ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture")
    ap.add_argument("--out-dir", default="dir-steering/out")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if not a.capture:
        ap.error("--capture is required")
    if not 1 <= a.k <= 4:
        ap.error("--k must be 1..4")
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
