#!/usr/bin/env python3
"""Gate a question-suffix template against the base one (change a000).

    template_gate.py --base-td r-td-1.jsonl --cand-td r-td-N.jsonl
                     --base-fx r-fx-1.jsonl --cand-fx r-fx-N.jsonl
                     [--base-rot r-rot-1.jsonl --cand-rot r-rot-N.jsonl]

Items are paired by id; an id of a base file missing from its candidate file
exits 2. Prints one JSON object with the deltas, `pass` and `failed`.
"""
import argparse
import json
import sys

import metrics


def load(path):
    return {r["id"]: r for r in map(json.loads, open(path)) if r.get("probs")}


def wrong(rows):
    return sum(metrics.top(r["probs"]) != r["label"] for r in rows)


def flip(plain, rot):
    return sum(metrics.top(plain[i]["probs"]) != metrics.top(r["probs"]) for i, r in rot.items()) / len(rot)


def gate(base_td, cand_td, base_fx, cand_fx, base_rot=None, cand_rot=None):
    for base, cand in ((base_td, cand_td), (base_fx, cand_fx), (base_rot or {}, cand_rot or {})):
        missing = [i for i in base if i not in cand]
        if missing:
            raise KeyError(f"{len(missing)} base ids missing from the candidate, first {missing[0]}")
    ids = list(base_td)
    b = [base_td[i] for i in ids]
    c = [cand_td[i] for i in ids]
    right = lambda r: metrics.top(r["probs"]) == r["label"]
    out = {
        "d_acc": metrics.accuracy(c) - metrics.accuracy(b),
        "d_nll": metrics.nll(c) - metrics.nll(b),
        "right_to_wrong": sum(right(x) and not right(y) for x, y in zip(b, c)),
        "wrong_to_right": sum(not right(x) and right(y) for x, y in zip(b, c)),
        "fx_wrong_more": wrong(cand_fx[i] for i in base_fx) - wrong(base_fx.values()),
        "legal_mass": sum(r["legal_mass"] for r in c) / len(c),
        "tokens_saved": sum(x["tokens"] - y["tokens"] for x, y in zip(b, c)) / len(ids),
    }
    limits = [("d_acc", out["d_acc"] >= -0.010), ("d_nll", out["d_nll"] <= 0.02),
              ("fx_wrong_more", out["fx_wrong_more"] <= 1), ("legal_mass", out["legal_mass"] >= 0.99),
              ("tokens_saved", out["tokens_saved"] >= 3.0)]
    if base_rot is not None:
        out["flip_base"] = flip(base_td, base_rot)
        out["flip_cand"] = flip(cand_td, cand_rot)
        limits.append(("flip_cand", out["flip_cand"] <= out["flip_base"] + 0.05))
    out["failed"] = [name for name, ok in limits if not ok]
    out["pass"] = not out["failed"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("base-td", "cand-td", "base-fx", "cand-fx"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--base-rot")
    ap.add_argument("--cand-rot")
    a = ap.parse_args()
    if bool(a.base_rot) != bool(a.cand_rot):
        ap.error("--base-rot and --cand-rot go together")
    rot = (load(a.base_rot), load(a.cand_rot)) if a.base_rot else (None, None)
    try:
        out = gate(load(a.base_td), load(a.cand_td), load(a.base_fx), load(a.cand_fx), *rot)
    except KeyError as e:
        print(f"template_gate: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
