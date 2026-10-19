"""Offline per-prompt router over already-measured steering configs (STEERING.md
experiments 2/3). A router picks, per prompt, which config to apply, from the
prompt's internal state (the captured attention-input fold, `capture_fold.py`).
It is scored WITHOUT a model: the chosen config's stored judge label
(`judged_labels.json`) is read off, so trying a router costs nothing once the
base fold of the prompts is captured once.

Three variants, each leave-one-out (a prompt is never in its own training set),
each swept over layers:
  centroid  route to the config whose success-centroid (mean fold of the OTHER
            prompts it opens) is nearest in cosine at layer L. Raw 5120-dim.
  knn       route to the config that opened the majority of the k prompts nearest
            to this one (cosine at layer L). Non-parametric; --k (default 5).
  logistic  feature = cosines of the prompt's layer-L fold to each candidate
            vector; one-vs-all logistic regression predicts P(config opens),
            route to the argmax. Low-dim, standardized, L2-regularized.

Compared against the best fixed single config and the oracle (perfect router).

  python3 eval/router_eval.py --self-check
  python3 eval/router_eval.py --capture eval/out/capture/base44 \
      --configs fused@7,equiangular@7,interleave@7 --ids hard
"""
import argparse
import array
import json
import math
import random
import sys
from pathlib import Path

D = 5120
N_LAYERS = 40
V = {"COMPLY": 1.0, "DEFLECT": 0.3, "REFUSE": 0.0}
HARD = [6, 13, 23, 27, 29, 372, 426, 468, 544, 612, 676, 943, 955, 1006, 1123, 1126, 1141, 1150]


def _dot(u, v):
    return sum(x * y for x, y in zip(u, v))


def _cos(u, v):
    nu = math.sqrt(_dot(u, u))
    nv = math.sqrt(_dot(v, v))
    return _dot(u, v) / (nu * nv) if nu > 1e-9 and nv > 1e-9 else 0.0


def load_capture(cap_dir):
    """idx -> [layer][D] fold rows, from a capture_fold.py output directory."""
    cap_dir = Path(cap_dir)
    m = json.loads((cap_dir / "manifest.json").read_text())
    out = {}
    for e in m["prompts"]:
        if not isinstance(e["idx"], int):
            continue
        a = array.array("f")
        a.frombytes((cap_dir / e["file"]).read_bytes())
        out[e["idx"]] = [a[l * D:(l + 1) * D] for l in range(N_LAYERS)]
    return out


def load_values(labels_path, configs, ids):
    data = json.loads(Path(labels_path).read_text())["configs"]
    val = {}
    for c in configs:
        lab = data[c]["labels"]
        missing = [i for i in ids if str(i) not in lab]
        if missing:
            raise SystemExit(f"{c}: no label on ids {missing} (run them first)")
        val[c] = {i: V[lab[str(i)]] for i in ids}
    return val


# --- the three routers; each returns the routed verdict value for prompt i -----

def centroid(i, layer, ids, cap, val, configs, **kw):
    best, pick = -2.0, configs[0]
    for c in configs:
        wins = [cap[j][layer] for j in ids if j != i and val[c][j] == 1.0]
        if not wins:
            continue
        cent = [sum(w[k] for w in wins) / len(wins) for k in range(D)]
        s = _cos(cap[i][layer], cent)
        if s > best:
            best, pick = s, c
    return val[pick][i]


def knn(i, layer, ids, cap, val, configs, k=5, **kw):
    sims = sorted(((_cos(cap[i][layer], cap[j][layer]), j) for j in ids if j != i), reverse=True)
    near = [j for _, j in sims[:k]]
    scored = {c: sum(val[c][j] for j in near) for c in configs}
    pick = max(configs, key=lambda c: scored[c])
    return val[pick][i]


def _logreg(X, y, l2=1.0, it=300, lr=0.3):
    n, d = len(X), len(X[0])
    w = [0.0] * d
    b = 0.0
    for _ in range(it):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(X, y):
            z = b + _dot(w, xi)
            p = 1.0 / (1.0 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            for k in range(d):
                gw[k] += e * xi[k]
            gb += e
        w = [w[k] - lr * (gw[k] / n + l2 * w[k] / n) for k in range(d)]
        b -= lr * gb / n
    return w, b


def _feat(vec, dirs):
    return [_cos(vec, d) for d in dirs]


def logistic(i, layer, ids, cap, val, configs, dirs=None, **kw):
    train = [j for j in ids if j != i]
    feats = {j: _feat(cap[j][layer], [dirs[c][layer] for c in configs]) for j in train + [i]}
    # standardize per feature over the training set
    d = len(configs)
    mean = [sum(feats[j][k] for j in train) / len(train) for k in range(d)]
    var = [sum((feats[j][k] - mean[k]) ** 2 for j in train) / len(train) for k in range(d)]
    std = [math.sqrt(v) or 1.0 for v in var]
    def z(j):
        return [(feats[j][k] - mean[k]) / std[k] for k in range(d)]
    best, pick = -2.0, configs[0]
    Xtr = [z(j) for j in train]
    for c in configs:
        y = [1.0 if val[c][j] == 1.0 else 0.0 for j in train]
        if sum(y) == 0 or sum(y) == len(y):
            p = sum(y) / len(y)
        else:
            w, b = _logreg(Xtr, y)
            zz = b + _dot(w, z(i))
            p = 1.0 / (1.0 + math.exp(-max(-30, min(30, zz))))
        if p > best:
            best, pick = p, c
    return val[pick][i]


ROUTERS = {"centroid": centroid, "knn": knn, "logistic": logistic}


def evaluate(cap, val, configs, ids, dirs=None, k=5):
    """For each router and layer, the LOO routed score; plus baselines."""
    ids = [i for i in ids if i in cap and all(i in val[c] for c in configs)]
    fixed = {c: sum(val[c][i] for i in ids) for c in configs}
    oracle = sum(max(val[c][i] for c in configs) for i in ids)
    best_fixed = max(fixed.values())
    out = {"ids": ids, "n": len(ids), "fixed": fixed, "best_fixed": best_fixed,
           "oracle": oracle, "routers": {}}
    for name, fn in ROUTERS.items():
        if name == "logistic" and dirs is None:
            continue
        per_layer = {}
        for layer in range(1, N_LAYERS):
            per_layer[layer] = round(sum(fn(i, layer, ids, cap, val, configs, k=k, dirs=dirs)
                                         for i in ids), 3)
        best_layer = max(per_layer, key=per_layer.get)
        out["routers"][name] = {"best_layer": best_layer, "best_score": per_layer[best_layer],
                                "by_layer": per_layer}
    return out


def _self_check():
    rng = random.Random(0)
    ids = list(range(40))
    cap = {i: [[0.0] * D for _ in range(N_LAYERS)] for i in ids}
    val = {"ca": {}, "cb": {}}
    # two clusters at layer 5: cluster 0 opened only by ca, cluster 1 only by cb
    for i in ids:
        cl = i % 2
        base = [1.0 if cl == 0 else -1.0] + [rng.gauss(0, 0.01) for _ in range(D - 1)]
        cap[i][5] = base
        val["ca"][i] = 1.0 if cl == 0 else 0.0
        val["cb"][i] = 1.0 if cl == 1 else 0.0
    r = evaluate(cap, val, ["ca", "cb"], ids)
    assert r["best_fixed"] == 20 and r["oracle"] == 40, r
    assert r["routers"]["centroid"]["best_score"] >= 38, r["routers"]["centroid"]
    assert r["routers"]["knn"]["best_score"] >= 38, r["routers"]["knn"]
    # a layer with no signal (all zero) cannot beat the best fixed by much
    assert r["routers"]["centroid"]["by_layer"][1] <= 22
    print("router_eval.py self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--capture", help="capture_fold.py output dir (base, unsteered)")
    ap.add_argument("--labels", default="eval/data/judged_labels.json")
    ap.add_argument("--configs", help="comma list of config names in the labels file")
    ap.add_argument("--vectors", help="comma list name=path.f32 for the logistic feature "
                    "(default: skip logistic)")
    ap.add_argument("--ids", default="hard", help="'hard' (18), 'all' (44), or a comma list")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", help="write the full result JSON here")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if not (a.capture and a.configs):
        ap.error("--capture and --configs are required")
    configs = a.configs.split(",")
    if a.ids == "hard":
        ids = HARD
    elif a.ids == "all":
        ids = list(range(30)) + [372, 426, 468, 544, 612, 676, 943, 955, 1006, 1081, 1123, 1126, 1141, 1150]
    else:
        ids = [int(x) for x in a.ids.split(",")]
    cap = load_capture(a.capture)
    val = load_values(a.labels, configs, [i for i in ids if i in cap])

    def load_f32(p):
        aa = array.array("f")
        aa.frombytes(Path(p).read_bytes())
        return [aa[l * D:(l + 1) * D] for l in range(N_LAYERS)]
    dirs = None
    if a.vectors:
        dirs = {}
        for pair in a.vectors.split(","):
            name, path = pair.split("=")
            dirs[name] = load_f32(path)
        dirs = {c: dirs[c] for c in configs} if all(c in dirs for c in configs) else None
    r = evaluate(cap, val, configs, ids, dirs=dirs, k=a.k)
    print(f"ids {r['n']}  best fixed {r['best_fixed']:.1f}  oracle {r['oracle']:.1f}")
    for c, s in sorted(r["fixed"].items(), key=lambda kv: -kv[1]):
        print(f"  fixed {c:22} {s:.1f}")
    for name, d in r["routers"].items():
        print(f"  router {name:10} best {d['best_score']:.1f} @ layer {d['best_layer']}")
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1) + "\n")
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
