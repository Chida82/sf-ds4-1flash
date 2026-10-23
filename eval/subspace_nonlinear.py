"""Is the refusal set curved? Two CPU checks on the 1017 capture (no model run).

A. Per layer, on a 64-dim PCA of the train rows, held-out AUC of a linear probe (logistic) vs a small MLP (64->64->1, tanh), refused
   vs complied (the hard pair) and refused vs benign; 3 seeds, 80/20 split. If the MLP does not beat
   the linear probe, refusal detection is linear here and gradient steering has no curvature to use.
B. The residual ids (q0@7 non-COMPLY, and the genuine think refuses): per layer, projection on q0,
   u1_l, d2_l as a z-score against the other refused prompts. "Under-dose" = q0 z is normal/low;
   "off-q0" = q0 normal but u1/d2 anomalous.

  emb-venv312/bin/python eval/subspace_nonlinear.py [--out eval/steering-comparison/subspace-1017-nonlinear.md]
  emb-venv312/bin/python eval/subspace_nonlinear.py --self-check
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_floor_direction as efd  # noqa: E402
import subspace_analysis as sa  # noqa: E402
from subspace_sim import auc, unit  # noqa: E402

RESIDUAL = {"nonthink": ["0", "18", "468"], "think": ["7", "544", "1123", "1126"]}
VECS = {"q0": "dir-steering/out/v41-mrfk-q0.f32", "u1": "dir-steering/out/v41-sub1017-u1.f32",
        "d2": "dir-steering/out/v41-sub1017-d2.f32"}
HIDDEN, EPOCHS, WD, PCA_K = 64, 500, 1e-3, 64


def fit(Xtr, ytr, Xte, hidden, seed):
    """logistic (hidden=0) or 1-hidden-layer MLP; returns held-out scores."""
    torch.manual_seed(seed)
    mu = Xtr.mean(0)
    P = np.linalg.svd(Xtr - mu, full_matrices=False)[2][:PCA_K].T  # both probes see the same PCA space
    Xtr, Xte = (Xtr - mu) @ P, (Xte - mu) @ P
    sd = Xtr.std() + 1e-6
    a, b = torch.tensor(Xtr / sd, dtype=torch.float32), torch.tensor(Xte / sd, dtype=torch.float32)
    y = torch.tensor(ytr, dtype=torch.float32)
    net = torch.nn.Linear(a.shape[1], 1) if hidden == 0 else torch.nn.Sequential(
        torch.nn.Linear(a.shape[1], hidden), torch.nn.Tanh(), torch.nn.Linear(hidden, 1))
    opt = torch.optim.Adam(net.parameters(), lr=1e-2, weight_decay=WD)
    w = torch.tensor([(1 - y.mean()) / y.mean()])  # balance classes
    for _ in range(EPOCHS):
        opt.zero_grad()
        torch.nn.functional.binary_cross_entropy_with_logits(net(a).squeeze(1), y, pos_weight=w).backward()
        opt.step()
    with torch.no_grad():
        return net(b).squeeze(1).numpy()


def probe_layer(Xl, pos, neg, seeds=(0, 1, 2)):
    """-> (auc_linear, auc_mlp) averaged over seeds, 80/20 split of pos and neg."""
    out = []
    for s in seeds:
        rng = np.random.default_rng(s)
        p, n = rng.permutation(pos), rng.permutation(neg)
        pt, nt = p[: len(p) // 5], n[: len(n) // 5]
        tr = np.concatenate([p[len(pt):], n[len(nt):]]); ytr = np.r_[np.ones(len(p) - len(pt)), np.zeros(len(n) - len(nt))]
        te = np.concatenate([pt, nt])
        r = []
        for h in (0, HIDDEN):
            sc = fit(Xl[tr], ytr, Xl[te], h, s)
            r.append(auc(sc[: len(pt)], sc[len(pt):]))
        out.append(r)
    return np.mean(out, 0)


def residual_z(X, ids, recs, vecs, layers):
    """z-score of the projection of each residual id on each vector, vs the other refused prompts."""
    refused = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is True])
    pos = {i: j for j, i in enumerate(ids)}
    rows = {}
    for name, V in vecs.items():
        for l in layers:
            v = unit(V[l])
            if not v.any():
                continue
            s = X[refused, l] @ v
            med, mad = np.median(s), np.median(np.abs(s - np.median(s))) * 1.4826 + 1e-6
            for grp, rid in RESIDUAL.items():
                for i in rid:
                    rows.setdefault((grp, i), {})[(name, l)] = float((X[pos[i], l] @ v - med) / mad)
    return rows


def report(X, ids, recs, vecs, layers):
    refused = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is True])
    complied = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is False])
    benign = np.array([j for j, i in enumerate(ids) if recs[i]["class"] == "benign"])
    L = ["# Linear vs MLP probe, held-out AUC (3 seeds); refused vs complied / refused vs benign", "",
         f"refused {len(refused)}, complied {len(complied)}, benign {len(benign)}; PCA {PCA_K}, MLP {HIDDEN} tanh, {EPOCHS} epochs, wd {WD}", "",
         "| layer | lin r/c | mlp r/c | gain | lin r/b | mlp r/b |", "|---|---:|---:|---:|---:|---:|"]
    for l in layers:
        c = probe_layer(X[:, l], refused, complied)
        b = probe_layer(X[:, l], refused, benign)
        L.append(f"| {l} | {c[0]:.3f} | {c[1]:.3f} | {c[1]-c[0]:+.3f} | {b[0]:.3f} | {b[1]:.3f} |")
        print(L[-1], flush=True)
    z = residual_z(X, ids, recs, vecs, layers)
    L += ["", "# Residual ids: z-score of projection vs the other refused (robust: median/MAD)", "",
          "| group | id | " + " | ".join(f"{n}@L{l}" for n in vecs for l in layers) + " |",
          "|---|---|" + "---:|" * (len(vecs) * len(layers))]
    for (grp, i), d in z.items():
        L.append(f"| {grp} | {i} | " + " | ".join(f"{d.get((n, l), float('nan')):+.1f}" for n in vecs for l in layers) + " |")
    return "\n".join(L)


def _self_check():
    rng = np.random.default_rng(0)
    D = 256
    d1 = unit(rng.standard_normal(D))
    pos = rng.standard_normal((200, D)).astype(np.float32); neg = rng.standard_normal((200, D)).astype(np.float32)
    # curved set: refusal = |x.d1| large (both signs) -> linear fails, MLP works
    pos += (4 * np.sign(rng.standard_normal(200)))[:, None] * d1
    Xl = np.concatenate([pos, neg])
    lin, mlp = probe_layer(Xl, np.arange(200), np.arange(200, 400), seeds=(0,))
    assert lin < 0.75 < mlp, (lin, mlp)
    pos2 = rng.standard_normal((200, D)).astype(np.float32) + 4 * d1  # linear set: both ~1.0
    lin2, mlp2 = probe_layer(np.concatenate([pos2, neg]), np.arange(200), np.arange(200, 400), seeds=(0,))
    assert lin2 > 0.95 and abs(mlp2 - lin2) < 0.05, (lin2, mlp2)
    print("subspace_nonlinear.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", default="eval/out-subspace-1017/capture")
    ap.add_argument("--layers", default="5,10,15,20,25,30,35")
    ap.add_argument("--out", default="eval/steering-comparison/subspace-1017-nonlinear.md")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    torch.set_num_threads(4)
    layers = [int(x) for x in a.layers.split(",")]
    ids, X, recs = sa.load_capture(a.capture)
    vecs = {n: np.fromfile(p, dtype=np.float32).reshape(efd.N_LAYERS, efd.D) for n, p in VECS.items()}
    txt = report(X, ids, recs, vecs, layers)
    Path(a.out).write_text(txt + "\n")
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
