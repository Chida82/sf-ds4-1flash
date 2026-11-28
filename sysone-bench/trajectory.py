#!/usr/bin/env python3
"""Think trajectory: input file for test_sysone and the curves it yields (change a025, step 0).

    trajectory.py --items A.jsonl [B.jsonl ...] --sys r-sys.jsonl ... --think r-think.jsonl ...
                  --n 200 --out traj.in
    trajectory.py --report traj.tsv --items A.jsonl ...

The first form picks up to N items: every item whose plain readout (sysone rows)
and thinking answer (think rows) disagree, then the rest at random (seed 0), and
writes them in the length-prefixed format `tests/test_sysone --think-trajectory`
reads. The second form reads its rows (id, n, kind, top, legal mass, logits) and
prints, for every budget N in steps of 32, the accuracy (state bootstrap
interval) and mean legal mass if the reasoning had been closed at N, plus the
stabilisation histogram and the go/no-go rule of the design.
"""
import argparse
import json
import random

import metrics
from run import label_key, load_items, option_keys


def field(text):
    b = (text or "").encode()
    return f"{len(b)}\n".encode() + b + b"\n"


def encode(it):
    q = it["question"]
    st = it["state"] if isinstance(it["state"], str) else json.dumps(it["state"], separators=(",", ":"), ensure_ascii=False)
    out = f"{it['id'].replace(' ', '_')} {q['type']} {len(option_keys(q))}\n".encode() + field(st) + field(q.get("instructions"))
    if q["type"] == "choice":
        out += b"".join(field(k) for k in q["criteria"])
        out += b"".join(field(v if isinstance(v, str) else json.dumps(v) if v else "") for v in q["criteria"].values())
    elif q["type"] == "noul":
        crit = q.get("criteria") or {}
        out += field("") + field("") + field(crit.get("true")) + field(crit.get("false"))
    else:
        out += b"".join(field("") for _ in q["criteria"]) + b"".join(field(str(c)) for c in q["criteria"])
    return out


def pick(items, sys_rows, think_rows, n):
    top = {r["id"]: metrics.top(r["probs"]) for r in sys_rows if r.get("probs")}
    ans = {r["id"]: r.get("answer") for r in think_rows}
    have = [it for it in items if it["id"] in top and it["id"] in ans]
    dis = [it for it in have if top[it["id"]] != ans[it["id"]]]
    rest = [it for it in have if top[it["id"]] == ans[it["id"]]]
    random.Random(0).shuffle(rest)
    return (dis + rest)[:n], len(dis)


def curves(rows, items, step=32):
    """{N: (rows as metrics wants them, mean legal mass)} and the per-item final row."""
    meta = {it["id"].replace(" ", "_"): it for it in items}
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r)
    by = {i: rs for i, rs in by.items() if rs[-1]["kind"] != "probe"}  # an item cut by the deadline has no final row
    final = {i: rs[-1] for i, rs in by.items()}
    top_n = max(r["n"] for r in rows)
    out = {}
    for n in range(0, top_n + step, step):
        sel, mass = [], []
        for i, rs in by.items():
            probes = [r for r in rs if r["kind"] == "probe" and r["n"] == n]
            r = probes[0] if probes else (final[i] if final[i]["n"] <= n else None)
            if r is None:
                continue
            it = meta[i]
            keys = option_keys(it["question"])
            sel.append({"state_id": it["state_id"], "label": label_key(it),
                        "probs": dict(zip(keys, metrics.softmax(r["logits"])))})
            mass.append(r["mass"])
        if len(sel) == len(by):
            out[n] = (sel, sum(mass) / len(mass))
    return out, final


def stabilisation(rows):
    """Per item, the first probe N from which the top no longer changes (final row included)."""
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r)
    res = {}
    for i, rs in by.items():
        if rs[-1]["kind"] == "probe":
            continue
        tops = [r["top"] for r in rs]
        k = len(tops) - 1
        while k > 0 and tops[k - 1] == tops[-1]:
            k -= 1
        res[i] = (rs[k]["n"], rs[-1]["n"])
    return res


def read_rows(path):
    rows = []
    for line in open(path):
        i, n, kind, top, mass, logits = line.rstrip("\n").split("\t")
        rows.append({"id": i, "n": int(n), "kind": kind, "top": int(top), "mass": float(mass),
                     "logits": [float(x) for x in logits.split(",")]})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", nargs="+", required=True)
    ap.add_argument("--sys", nargs="*", default=[])
    ap.add_argument("--think", nargs="*", default=[])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out")
    ap.add_argument("--report")
    a = ap.parse_args()
    items = [it for p in a.items for it in load_items(p)]
    if a.report:
        rows = read_rows(a.report)
        cur, final = curves(rows, items)
        base = metrics.accuracy(cur[0][0]) if 0 in cur else None
        print("| N | n | accuracy | 95% CI | ECE | mean legal mass |\n|---|---|---|---|---|---|")
        for n, (sel, mass) in sorted(cur.items()):
            lo, hi = metrics.bootstrap_accuracy(sel)
            print(f"| {n} | {len(sel)} | {metrics.accuracy(sel):.3f} | {lo:.3f}-{hi:.3f} | {metrics.ece(sel):.3f} | {mass:.3f} |")
        kinds = {}
        for r in final.values():
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        nat = sorted(r["n"] for r in final.values())
        print(f"\nend of reasoning: {kinds}; reasoning tokens p50 {metrics.percentile(nat, 0.5):.0f}, "
              f"p95 {metrics.percentile(nat, 0.95):.0f}")
        st = stabilisation(rows)
        early = sum(s < 0.25 * e for s, e in st.values() if e)
        print(f"stabilised before a quarter of their length: {early}/{len(st)}")
        hist = {}
        for s, _ in st.values():
            hist[s] = hist.get(s, 0) + 1
        print("stabilisation N histogram:", dict(sorted(hist.items())))
        mass64 = cur.get(64, (None, float("nan")))[1]
        above = [n for n, (sel, _) in cur.items() if 0 < n <= 256 and base is not None
                 and metrics.bootstrap_accuracy(sel)[0] > base]
        print(f"rule: legal mass at 64 = {mass64:.3f} (need >= 0.5); N <= 256 with interval wholly above N=0: "
              f"{above or 'none'} -> {'GO' if mass64 >= 0.5 and above else 'NO GO'}")
        return 0
    sys_rows = [json.loads(l) for p in a.sys for l in open(p) if l.strip()]
    think_rows = [json.loads(l) for p in a.think for l in open(p) if l.strip()]
    chosen, n_dis = pick(items, sys_rows, think_rows, a.n)
    with open(a.out, "wb") as f:
        for it in chosen:
            f.write(encode(it))
    print(f"trajectory: {len(chosen)} items ({n_dis} where readout and thinking disagree) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
