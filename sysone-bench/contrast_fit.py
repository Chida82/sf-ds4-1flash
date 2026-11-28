#!/usr/bin/env python3
"""Prior contrast p = softmax((z - beta * u) / T0), fitted and tested (change a020).

    contrast_fit.py --items A.jsonl ... --results r-sys.jsonl ... [--blank blank.jsonl ...]

z: an item's option logits (run.py sysone rows). u, the prior, centred over
the options:
- content-free: the logits of the same question with the state
  "(no state given)" (`run.py --blank-state` rows, id = question key);
- batch: the mean log-softmax of z over the fit-half states asked the same
  question (the item itself excluded); needs 8 of them, else no batch prior.

Split by state hash (fit.py's): even fits T0 per type at beta 0, then beta on
the grid by NLL; odd reports beta* against beta 0 with paired state-level
bootstrap intervals of the NLL and accuracy differences. `score` is reported
but outside the gate. Prints one table and the gate of the design.
"""
import argparse
import json
import math
import random

import fit
import metrics
from run import label_key, load_items, option_keys, question_key

BETAS = (0, 0.25, 0.5, 0.75, 1, 1.25, 1.5)
MIN_BATCH = 8


def centred(v):
    m = sum(v) / len(v)
    return [x - m for x in v]


def log_softmax(v):
    m = max(v)
    s = math.log(sum(math.exp(x - m) for x in v)) + m
    return [x - s for x in v]


def build(items, results, blank):
    """Rows {id, state_id, type, qk, keys, label, z, u_free, fit}; batch prior added by add_batch."""
    res = {r["id"]: r for r in results if r.get("logits")}
    rows = []
    for it in items:
        r = res.get(it["id"])
        if r is None:
            continue
        keys = option_keys(it["question"])
        qk = question_key(it["question"])
        b = blank.get(qk)
        rows.append({"id": it["id"], "state_id": it["state_id"], "type": it["question"]["type"], "qk": qk,
                     "keys": keys, "label": label_key(it), "z": [r["logits"][k] for k in keys],
                     "u_free": centred([b["logits"][k] for k in keys]) if b else None,
                     "fit": fit.is_even(it["state_id"])})
    return rows


def add_batch(rows):
    by = {}
    for r in rows:
        if r["fit"]:
            by.setdefault(r["qk"], []).append(r)
    for r in rows:
        others = [o for o in by.get(r["qk"], []) if o["state_id"] != r["state_id"]]
        if len(others) < MIN_BATCH:
            r["u_batch"] = None
            continue
        ls = [log_softmax(o["z"]) for o in others]
        r["u_batch"] = centred([sum(col) / len(ls) for col in zip(*ls)])


def scored(r, prior, beta, t):
    u = r[prior] if beta else None
    z = [x - beta * y for x, y in zip(r["z"], u)] if u else r["z"]
    return {"state_id": r["state_id"], "label": r["label"], "probs": dict(zip(r["keys"], metrics.softmax(z, t)))}


def item_nll(s):
    return -math.log(max(s["probs"].get(s["label"], 0.0), 1e-12))


def paired(a, b, n=2000, seed=0):
    """95% intervals of mean(b - a) for NLL and accuracy, resampling states."""
    by = {}
    for x, y in zip(a, b):
        by.setdefault(x["state_id"], []).append((item_nll(y) - item_nll(x),
                                                 (metrics.top(y["probs"]) == y["label"]) - (metrics.top(x["probs"]) == x["label"])))
    groups = list(by.values())
    rng = random.Random(seed)
    dn, da = [], []
    for _ in range(n):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        k = sum(len(g) for g in pick)
        dn.append(sum(d for g in pick for d, _ in g) / k)
        da.append(sum(d for g in pick for _, d in g) / k)
    dn.sort()
    da.sort()
    lo, hi = int(0.025 * n), int(0.975 * n) - 1
    return (dn[lo], dn[hi]), (da[lo], da[hi])


def evaluate(rows, prior):
    """Per type: T0, beta*, test-half figures. Only rows that have the prior."""
    out = {}
    for t in ("noul", "choice", "score"):
        sel = [r for r in rows if r["type"] == t and r.get(prior)]
        fit_rows = [r for r in sel if r["fit"]]
        test = [r for r in sel if not r["fit"]]
        if len(fit_rows) < 10 or not test:
            continue
        t0 = fit.fit_type([{"logits": dict(zip(r["keys"], r["z"])), "label": r["label"],
                            "probs": dict(zip(r["keys"], metrics.softmax(r["z"])))} for r in fit_rows])
        best = min(BETAS, key=lambda b: metrics.nll([scored(r, prior, b, t0) for r in fit_rows]))
        base = [scored(r, prior, 0, t0) for r in test]
        new = [scored(r, prior, best, t0) for r in test]
        (nlo, nhi), (alo, ahi) = paired(base, new)
        out[t] = {"n": len(test), "T0": t0, "beta": best, "nll0": metrics.nll(base), "nll": metrics.nll(new),
                  "acc0": metrics.accuracy(base), "acc": metrics.accuracy(new), "dnll": (nlo, nhi), "dacc": (alo, ahi)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", nargs="+", required=True)
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--blank", nargs="*", default=[])
    a = ap.parse_args()
    items = [it for p in a.items for it in load_items(p)]
    results = [json.loads(l) for p in a.results for l in open(p) if l.strip()]
    blank = {r["id"]: r for p in a.blank for r in map(json.loads, open(p)) if r.get("logits")}
    rows = build(items, results, blank)
    add_batch(rows)
    print("| prior | type | test n | T0 | beta* | NLL beta0 | NLL beta* | dNLL 95% CI | acc beta0 | acc beta* | dacc 95% CI | gate |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for prior in ("u_free", "u_batch"):
        for t, e in evaluate(rows, prior).items():
            keep = t != "score" and e["dnll"][1] < 0 and e["dacc"][1] >= -0.010
            print(f"| {'content-free' if prior == 'u_free' else 'batch'} | {t} | {e['n']} | {e['T0']:.2f} | {e['beta']} | "
                  f"{e['nll0']:.4f} | {e['nll']:.4f} | {e['dnll'][0]:+.4f} to {e['dnll'][1]:+.4f} | {e['acc0']:.3f} | "
                  f"{e['acc']:.3f} | {e['dacc'][0]:+.3f} to {e['dacc'][1]:+.3f} | {'keep' if keep else 'drop' if t != 'score' else 'not gated'} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
