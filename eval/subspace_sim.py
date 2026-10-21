"""What is in the refusal subspace, measured on held-out prompts (CPU, a few minutes).

Groups (fixed roles): the refused harmful prompts build the basis (train 800 / test 200 by seed),
the complied harmful prompts (136) and the benign (200) are controls and never enter the basis;
the benign mean is the origin. Per layer:
  - split-half stability of u1..u3 (|cos| between the bases of two 400-prompt halves): a real
    direction scores ~0.9+, sampling noise ~0 -> k per band;
  - |cos(u1_l, u1_l+1)|: one direction carried along the residual stream, or band-specific;
  - LDA direction w = (S + lam*tr(S)/d*I)^-1 (mu_ref - mu_ben), S pooled within-class covariance;
  - mismatch of a fixed vector v on each test prompt: 1 - (v.x)^2 / ||U3^T x||^2 with x centred,
    i.e. the share of the prompt's in-subspace refusal that v does NOT point at;
  - detector AUCs (refused-test vs complied, refused-test vs benign) of the scalars u1.x, w.x, ||U3^T x||.
Writes <out>.md and <out>-dirs.npz (u1 and LDA on ALL 1000, ready to be written as vectors).

  emb-venv312/bin/python eval/subspace_sim.py [--capture ...] [--out eval/steering-comparison/subspace-1017-sim]
  emb-venv312/bin/python eval/subspace_sim.py --self-check
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_floor_direction as efd  # noqa: E402
import subspace_analysis as sa  # noqa: E402

K = 3
LAM = 0.1


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.divide(v, n, out=np.zeros_like(v), where=n > 0)


def basis(R, k=K):
    _, s, vt = np.linalg.svd(R, full_matrices=False)
    return vt[:k], s[:k]


def lda(R, B, delta, lam=LAM):
    """R, B centred on their own means (refused, benign); delta = mu_ref - mu_ben -> unit direction."""
    S = (R.T @ R + B.T @ B) / (len(R) + len(B) - 2)
    S[np.diag_indices_from(S)] += lam * np.trace(S) / S.shape[0]
    return unit(np.linalg.solve(S, delta))


def auc(pos, neg):
    """Rank AUC of score arrays: P(score_pos > score_neg)."""
    a = np.concatenate([pos, neg])
    r = np.empty(len(a)); r[np.argsort(a, kind="stable")] = np.arange(1, len(a) + 1)
    _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    r = np.bincount(inv, weights=r)[inv] / cnt[inv]  # average rank on ties
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def layer_stats(Xl, groups, vectors, rng):
    """Xl: (n, D) one layer. groups: dict name -> index array (refused_train, refused_test,
    complied, benign). vectors: name -> (D,) unit fixed direction or None. -> dict of numbers."""
    tr, te, co, be = (groups[g] for g in ("refused_train", "refused_test", "complied", "benign"))
    mb = Xl[be].mean(0)
    R = Xl[tr] - mb
    U, s = basis(R)
    U = U * np.sign(U @ R.mean(0))[:, None]  # orient toward refusal (SVD signs are arbitrary)
    half = rng.permutation(len(tr)); A, B = half[: len(tr) // 2], half[len(tr) // 2:]
    UA, _ = basis(R[A]); UB, _ = basis(R[B])
    stab = [abs(float(UA[j] @ UB[j])) for j in range(K)]
    w = lda(R - R.mean(0), Xl[be] - mb, R.mean(0))
    dm = unit(R.mean(0))
    out = {"stab": stab, "u1": U[0], "lda": w, "dm": dm, "cos_u1_lda": abs(float(U[0] @ w)),
           "cos_u1_dm": abs(float(U[0] @ dm))}
    Xt = Xl[te] - mb
    inU = np.linalg.norm(Xt @ U.T, axis=1)
    out["mismatch"] = {}
    for name, v in {**vectors, "u1": U[0], "lda": w}.items():
        if v is None:
            continue
        m = 1 - (Xt @ v) ** 2 / np.maximum(inU ** 2, 1e-12)
        out["mismatch"][name] = (float(np.median(m)), float((m > 0.02).mean()), float((m > 0.5).mean()))
    sc = {"u1": lambda idx: (Xl[idx] - mb) @ U[0], "lda": lambda idx: (Xl[idx] - mb) @ w,
          "normU3": lambda idx: np.linalg.norm((Xl[idx] - mb) @ U.T, axis=1)}
    out["auc"] = {n: (auc(f(te), f(co)), auc(f(te), f(be))) for n, f in sc.items()}
    return out


def report(X, recs, ids, vectors, seed=0, layers=None, external=None):
    """external=(ids2, X2, recs2): basis on ALL refused of the capture, tests on the external
    refused/complied (the 383 SORRY-Bench); benign stays the capture's."""
    rng = np.random.default_rng(seed)
    refused = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is True])
    benign = np.array([j for j, i in enumerate(ids) if recs[i]["class"] == "benign"])
    if external is None:
        perm = rng.permutation(len(refused)); n_te = len(refused) // 5
        groups = {"refused_test": refused[perm[:n_te]], "refused_train": refused[perm[n_te:]],
                  "complied": np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is False]),
                  "benign": benign}
    else:
        ids2, X2, recs2 = external
        n0 = len(ids); X = np.concatenate([X, X2])
        groups = {"refused_train": refused, "benign": benign,
                  "refused_test": np.array([n0 + j for j, i in enumerate(ids2) if recs2[i].get("refusal") is True]),
                  "complied": np.array([n0 + j for j, i in enumerate(ids2) if recs2[i].get("refusal") is False])}
    layers = layers or range(1, X.shape[1])
    rows, u1s, ldas = [], {}, {}
    for l in layers:
        st = layer_stats(X[:, l], groups, {n: (unit(V[l]) if np.linalg.norm(V[l]) else None) for n, V in vectors.items()}, rng)
        rows.append((l, st)); u1s[l], ldas[l] = st["u1"], st["lda"]
    L = ["# Refusal subspace, held-out measures", "",
         f"refused train {len(groups['refused_train'])} / test {len(groups['refused_test'])}, complied {len(groups['complied'])}, "
         f"benign {len(groups['benign'])}; k={K}, LDA shrinkage {LAM}", "",
         "## Stability (split-half |cos| of u1 u2 u3), u1 vs next layer, u1 vs LDA, u1 vs diff-means", "",
         "| layer | u1 | u2 | u3 | u1·u1(l+1) | u1·lda | u1·dm |", "|---|---:|---:|---:|---:|---:|---:|"]
    for (l, st), nxt in zip(rows, rows[1:] + [None]):
        c = abs(float(st["u1"] @ nxt[1]["u1"])) if nxt else float("nan")
        L.append(f"| {l} | " + " | ".join(f"{x:.2f}" for x in st["stab"]) + f" | {c:.2f} | {st['cos_u1_lda']:.2f} | {st['cos_u1_dm']:.2f} |")
    names = list(rows[0][1]["mismatch"])
    L += ["", "## Mismatch on the 200 held-out refused: median, share > 2%, share > 50% (share of the in-subspace refusal the vector misses)", "",
          "| layer | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for l, st in rows:
        L.append(f"| {l} | " + " | ".join(f"{m[0]:.2f} / {m[1]:.0%} / {m[2]:.0%}" for m in (st["mismatch"][n] for n in names)) + " |")
    L += ["", "## Detector AUC (refused-test vs complied, refused-test vs benign)", "",
          "| layer | u1·x | lda·x | ‖U3ᵀx‖ |", "|---|---|---|---|"]
    for l, st in rows:
        L.append(f"| {l} | " + " | ".join(f"{a[0]:.2f} / {a[1]:.2f}" for a in (st["auc"][n] for n in ("u1", "lda", "normU3"))) + " |")
    return "\n".join(L), u1s, ldas


def final_dirs(X, recs, ids):
    """u1 and LDA per layer on ALL refused (the basis to write as vectors); row 0 zero."""
    refused = [j for j, i in enumerate(ids) if recs[i].get("refusal") is True]
    benign = [j for j, i in enumerate(ids) if recs[i]["class"] == "benign"]
    u1 = np.zeros((X.shape[1], efd.D), np.float32); w = np.zeros_like(u1)
    for l in range(1, X.shape[1]):
        mb = X[benign, l].mean(0); R = X[refused, l] - mb
        U, _ = basis(R, 1); u1[l] = U[0] * np.sign(U[0] @ R.mean(0))  # sign: toward refusal
        w[l] = lda(R - R.mean(0), X[benign, l] - mb, R.mean(0))
    return u1, w


def _self_check():
    rng = np.random.default_rng(0)
    L, D = 4, efd.D
    d1 = unit(rng.standard_normal(D)); d2 = unit(rng.standard_normal(D))
    ids = [f"b{k}" for k in range(60)] + [str(i) for i in range(300)]
    X = (rng.standard_normal((360, L, D)) * 0.02).astype(np.float32)
    recs = {}
    for j, i in enumerate(ids):
        if i.startswith("b"):
            recs[i] = {"class": "benign", "refusal": None}; continue
        ref = j % 4 != 0
        recs[i] = {"class": "pool", "refusal": ref}
        if ref:
            X[j] += 3 * d1 + rng.normal(0, 1) * d2
    txt, u1s, ldas = report(X, recs, ids, {"v": np.tile(d1, (L, 1))}, layers=[1, 2])
    assert abs(float(u1s[1] @ d1)) > 0.95 and abs(float(ldas[1] @ d1)) > 0.8, (u1s[1] @ d1, ldas[1] @ d1)
    assert "| 1 | 1.00 | " in txt, txt  # u1 stable across halves
    assert float(txt.split("| 1 | ")[2].split(" / ")[0]) < 0.1, txt  # v (= d1) mismatch small
    assert auc(np.array([3, 4, 5]), np.array([1, 2])) == 1.0 and abs(auc(np.array([1, 2]), np.array([1, 2])) - 0.5) < 1e-9
    u1, w = final_dirs(X, recs, ids)
    assert u1.shape == (L, D) and not u1[0].any() and float(u1[1] @ d1) > 0.95
    print("subspace_sim.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", default="eval/out-subspace-1017/capture")
    ap.add_argument("--position", default="rows", choices=["rows", "gen", "pmean"])
    ap.add_argument("--out", default="eval/steering-comparison/subspace-1017-sim")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--external", help="capture dir of an external test set (e.g. SORRY-Bench): basis on all "
                    "capture refused, tests on the external refused/complied; writes <out>-external.md only")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    ids, X, recs = sa.load_capture(a.capture, a.position)
    vectors = {n: np.fromfile(p, dtype=np.float32).reshape(efd.N_LAYERS, efd.D)
               for n, p in sa.VECTORS.items() if n in ("fused", "abliteration") and Path(p).exists()}
    if a.external:
        txt, _, _ = report(X, recs, ids, vectors, a.seed, external=sa.load_capture(a.external, a.position))
        Path(a.out + "-external.md").write_text(txt + "\n")
        print(txt)
        return 0
    txt, _, _ = report(X, recs, ids, vectors, a.seed)
    Path(a.out + ".md").write_text(txt + "\n")
    u1, w = final_dirs(X, recs, ids)
    np.savez_compressed(a.out + "-dirs.npz", u1=u1, lda=w, position=a.position)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
