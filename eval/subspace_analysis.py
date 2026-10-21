"""Refusal subspace from a capture_subspace.py directory (no model, CPU, ~1 min).

Per layer: R = folds of refused harmful prompts minus the benign mean; SVD(R) gives the
subspace basis and spectrum. Reported: variance share of the top 5 directions, the cosine of
each known vector's row (abliteration, msuiche, fused, equiangular, interleave) with the top-3
directions and with the difference-of-means direction, and the drift of the 44 study folds
against an older capture (cos old/new per layer, if --old is given). Archives basis+spectrum
in <out>.npz and writes a markdown report.

  python3 eval/subspace_analysis.py --capture eval/out-subspace-1017/capture \
      --old eval/out/capture/base44 --out eval/steering-comparison/subspace-1017
  python3 eval/subspace_analysis.py --self-check
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_floor_direction as efd  # noqa: E402

VECTORS = {"abliteration": "dir-steering/vectors/v41-abliteration-attn.f32",
           "msuiche": "dir-steering/vectors/v41-msuiche.f32",
           "fused": "dir-steering/vectors/v41-fused-msuiche-audreyt-denoise.f32",
           "equiangular": "dir-steering/out/v41-poly-equiangular.f32",
           "interleave": "dir-steering/out/v41-poly-interleave.f32"}
STUDY = [str(i) for i in range(30)] + [str(i) for i in (372, 426, 468, 544, 612, 676, 943, 955, 1006, 1081, 1123, 1126, 1141, 1150)]
K = 8


def load_capture(d, position="rows"):
    """-> (ids, X (n,40,5120), recs by id). position: rows (decision token), gen (first
    generated token) or pmean (mean over prompt tokens), the three files capture_subspace writes."""
    recs = {}
    for p in sorted(Path(d).glob("*.json")):
        if p.stem == "manifest":
            continue
        r = json.loads(p.read_text())
        if (Path(d) / f"{position}_{r['idx']}.f32").exists():
            recs[str(r["idx"])] = r
    ids = sorted(recs)
    X = np.stack([np.fromfile(Path(d) / f"{position}_{i}.f32", dtype=np.float32).reshape(efd.N_LAYERS, efd.D) for i in ids])
    return ids, X, recs


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.divide(v, n, out=np.zeros_like(v), where=n > 0)


def subspace(X, refused, benign, k=K):
    """per layer: basis (k,5120), singular values (k), variance share (k), diff-of-means dir."""
    L = X.shape[1]
    U = np.zeros((L, k, efd.D), np.float32); S = np.zeros((L, k)); share = np.zeros((L, k))
    dom = np.zeros((L, efd.D), np.float32)
    for l in range(L):
        mb = X[benign, l].mean(0)
        R = X[refused, l] - mb
        _, s, vt = np.linalg.svd(R, full_matrices=False)
        kk = min(k, len(s))
        U[l, :kk], S[l, :kk] = vt[:kk], s[:kk]
        share[l, :kk] = s[:kk] ** 2 / (s ** 2).sum()
        dom[l] = unit(R.mean(0))
    return U, S, share, dom


def report(ids, X, recs, vectors, old=None):
    refused = [j for j, i in enumerate(ids) if recs[i].get("refusal") is True]
    comply = [j for j, i in enumerate(ids) if recs[i].get("refusal") is False]
    benign = [j for j, i in enumerate(ids) if recs[i]["class"] == "benign"]
    U, S, share, dom = subspace(X, refused, benign)
    L = ["# Refusal subspace", "", f"prompts: {len(ids)} (refused {len(refused)}, complied {len(comply)}, benign {len(benign)})", ""]
    L += ["## Spectrum per layer (variance share of the top 5 of SVD(refused - benign mean))", "",
          "| layer | s1 | s2 | s3 | s4 | s5 | top1 share | top2 cum | top3 cum |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for l in range(X.shape[1]):
        L.append(f"| {l} | " + " | ".join(f"{share[l, j]:.3f}" for j in range(5)) +
                 f" | {share[l, 0]:.3f} | {share[l, :2].sum():.3f} | {share[l, :3].sum():.3f} |")
    L += ["", "## Known vectors vs the basis (|cos| with u1, u2, u3; cos with diff-of-means), layer 1..39", ""]
    for name, V in vectors.items():
        L += [f"### {name}", "", "| layer | u1 | u2 | u3 | in-span(3) | diff-means |", "|---|---:|---:|---:|---:|---:|"]
        for l in range(1, X.shape[1]):
            v = V[l]
            if not np.linalg.norm(v):
                L.append(f"| {l} | - | - | - | - | - |"); continue
            v = v / np.linalg.norm(v)
            c = U[l, :3] @ v
            L.append(f"| {l} | {abs(c[0]):.2f} | {abs(c[1]):.2f} | {abs(c[2]):.2f} | {np.sqrt((c ** 2).sum()):.2f} | {dom[l] @ v:.2f} |")
        L.append("")
    if comply:
        dcm = unit(X[refused].mean(0) - X[comply].mean(0))
        L += ["## refused-vs-complied (harmful only) direction vs refused-vs-benign direction, cos per layer", "",
              " ".join(f"L{l}:{dcm[l] @ dom[l]:.2f}" for l in range(1, X.shape[1])), ""]
    if old is not None:
        oids, OX, _ = old
        common = [i for i in STUDY if i in ids and i in oids]
        if common:
            a = X[[ids.index(i) for i in common]]; b = OX[[oids.index(i) for i in common]]
            cos = (unit(a) * unit(b)).sum(-1)  # (n, L)
            L += [f"## Drift of the study folds, old capture vs this one ({len(common)} ids): cos per layer, mean (min)", "",
                  " ".join(f"L{l}:{cos[:, l].mean():.3f}({cos[:, l].min():.2f})" for l in range(1, X.shape[1])), ""]
    return "\n".join(L), (U, S, share, dom)


def _self_check():
    rng = np.random.default_rng(0)
    L, D = efd.N_LAYERS, efd.D
    d1 = unit(rng.standard_normal(D)); d2 = unit(rng.standard_normal(D))
    ids = [f"b{k}" for k in range(10)] + [str(i) for i in range(30)]
    X = rng.standard_normal((40, L, D)).astype(np.float32) * 0.01
    recs = {}
    for j, i in enumerate(ids):
        if i.startswith("b"):
            recs[i] = {"idx": i, "class": "benign", "refusal": None}
        else:
            refused = j % 3 != 0
            recs[i] = {"idx": i, "class": "study", "refusal": refused}
            if refused:
                X[j] += 5 * d1 + 2 * (1 if j % 2 else -1) * d2
    txt, (U, S, share, dom) = report(ids, X, recs, {"v": np.tile(d1, (L, 1))}, old=(ids, X.copy(), recs))
    assert abs(float(abs(U[3, 0] @ d1))) > 0.95, U[3, 0] @ d1
    assert share[3, :2].sum() > 0.9, share[3]
    assert "| 3 | 1.00 |" in txt and "L3:1.000(1.00)" in txt, txt[-600:]
    print("subspace_analysis.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", default="eval/out-subspace-1017/capture")
    ap.add_argument("--old", default="eval/out/capture/base44", help="older capture dir for the drift block; '' to skip")
    ap.add_argument("--out", default="eval/steering-comparison/subspace-1017", help="writes <out>.md and <out>.npz")
    ap.add_argument("--position", default="rows", choices=["rows", "gen", "pmean"])
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    ids, X, recs = load_capture(a.capture, a.position)
    vectors = {n: np.fromfile(p, dtype=np.float32).reshape(efd.N_LAYERS, efd.D) for n, p in VECTORS.items() if Path(p).exists()}
    old = None
    if a.old and Path(a.old, "manifest.json").exists():
        m = json.loads(Path(a.old, "manifest.json").read_text())
        oids = [str(p["idx"]) for p in m["prompts"] if p.get("file")]
        OX = np.stack([np.fromfile(Path(a.old, f"rows_{i}.f32"), dtype=np.float32).reshape(efd.N_LAYERS, efd.D) for i in oids])
        old = (oids, OX, None)
    txt, (U, S, share, dom) = report(ids, X, recs, vectors, old)
    Path(a.out + ".md").write_text(txt + "\n")
    np.savez_compressed(a.out + ".npz", ids=np.array(ids), basis=U, singular=S, share=share, diff_means=dom,
                        refused=np.array([recs[i].get("refusal") is True for i in ids]))
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
