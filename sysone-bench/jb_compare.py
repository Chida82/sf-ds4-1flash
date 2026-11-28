#!/usr/bin/env python3
"""Paired comparison with a jevbench system on the same public items (change a010).

    jb_compare.py --per-task jevbench-v1.2-per-task.json --results r.jsonl [--system KEY ...]
    jb_compare.py --per-task FILE --list

The per-task file holds, per system, `public_tasks`: {item id: [outcome, confidence]}
with outcome c (correct), w (wrong), f (failed, scored wrong), n (not attempted).
Our results are run.py rows; a row is right when its top option (sysone) or its
parsed answer (think) equals the label; a missing row, a parse failure or an HTTP
error is wrong. Only items both sides attempted are compared ('n' is dropped).
Prints accuracy of both, the discordant pairs and the exact two-sided sign test.
"""
import argparse
import json
import math
import sys

import metrics


def right(r):
    if "answer" in r:  # think/gen row
        return r["answer"] is not None and r["answer"] == r["label"]
    return bool(r.get("probs")) and metrics.top(r["probs"]) == r["label"]


def sign_test(b, c):
    """Exact two-sided binomial test of b against c discordant pairs, p = 0.5."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(tasks, results):
    ours = {r["id"]: right(r) for r in results}
    pairs = [(ours.get(i, False), o[0] == "c") for i, o in tasks.items() if o[0] != "n"]
    b = sum(x and not y for x, y in pairs)
    c = sum(y and not x for x, y in pairs)
    n = len(pairs)
    return {"n": n, "ours": sum(x for x, _ in pairs), "theirs": sum(y for _, y in pairs),
            "ours_only": b, "theirs_only": c, "p": sign_test(b, c)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-task", required=True)
    ap.add_argument("--results")
    ap.add_argument("--system", action="append", default=[])
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    systems = json.load(open(a.per_task))["systems"]
    if a.list:
        for k, v in sorted(systems.items(), key=lambda kv: -sum(o[0] == "c" for o in kv[1]["public_tasks"].values())):
            pt = v["public_tasks"]
            print(f"{sum(o[0] == 'c' for o in pt.values()):4d}/{len(pt)}  {k}  {v['display']}")
        return 0
    if not a.results or not a.system:
        ap.error("--results and --system are required without --list")
    results = [json.loads(l) for l in open(a.results) if l.strip()]
    print("| system | n | ours | theirs | ours only | theirs only | sign test p |\n|---|---|---|---|---|---|---|")
    for k in a.system:
        if k not in systems:
            print(f"jb_compare: no system {k!r} (see --list)", file=sys.stderr)
            return 2
        s = compare(systems[k]["public_tasks"], results)
        print(f"| {systems[k]['display']} | {s['n']} | {s['ours']} ({s['ours'] / s['n']:.3f}) | "
              f"{s['theirs']} ({s['theirs'] / s['n']:.3f}) | {s['ours_only']} | {s['theirs_only']} | {s['p']:.3g} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
