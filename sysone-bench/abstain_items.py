#!/usr/bin/env python3
"""Abstention baseline (change 820): does the model know when the state lacks the answer?

    abstain_items.py make --fixtures sysone-bench/fixtures-it.jsonl --synthetic 140 --out abstain.jsonl
    run.py --mode sysone --items abstain.jsonl --out abstain-results.jsonl
    abstain_items.py score --items abstain.jsonl --results abstain-results.jsonl

Every source item carries an `evidence` sentence (the fixtures do; the synthetic
English items are built that way). Its twin replaces that sentence with a neutral
one of about the same length. Each state is asked three questions in one request:
the original (detectors 1 and 4), the original with an extra option
"insufficient: the state does not say" (detector 2), and a companion noul
"The state contains the information needed to answer: ..." (detector 3).
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics  # noqa: E402

NEUTRAL = [
    "The message was logged by the system this morning.",
    "This note was filed automatically with the others.",
    "The record was copied from the weekly export.",
    "Il messaggio è stato archiviato insieme agli altri.",
    "La nota è stata registrata automaticamente stamattina.",
]
INSUFFICIENT = "insufficient"
INSUFFICIENT_TEXT = "the state does not say"

NAMES = ["Anna", "Ben", "Carla", "David", "Elena", "Frank", "Giulia", "Hugo", "Irene", "Jonas"]
# (type, instructions, criteria, context, [(evidence, label)], tail)
TEMPLATES = [
    ("noul", "The parcel was delivered.", None, "Shipment {n} for {name}.",
     [("The courier marked the parcel as delivered at {h}:05 and took a photo at the door.", True),
      ("The courier could not deliver the parcel and will try again tomorrow.", False)], "Customer notified by email."),
    ("noul", "The invoice has been paid.", None, "Invoice {n} from supplier {name} Ltd, {amount} EUR.",
     [("The bank confirmed the transfer for this invoice on the {d}th.", True),
      ("The invoice is still unpaid and the due date is the {d}th.", False)], "No other notes."),
    ("noul", "The employee is on leave today.", None, "Status update for {name} in accounting.",
     [("{name} is on annual leave until the {d}th and is not reading email.", True),
      ("{name} is working from the office today and available all afternoon.", False)], "Calendar synced at {h}:00."),
    ("choice", "Route the request to a team.", {"billing": "charges, invoices, refunds", "technical": "bugs, outages, login problems",
     "sales": "new purchases and quotes"}, "Ticket {n} opened by {name}.",
     [("The customer was charged twice for the same order and wants the duplicate reversed.", "billing"),
      ("The customer cannot log in because the app crashes on the password screen.", "technical"),
      ("The customer wants a quote for {amount} licences for their new office.", "sales")], "Priority set automatically."),
    ("choice", "Which day is the meeting?", {"monday": None, "wednesday": None, "friday": None}, "Note from {name} to the team.",
     [("The planning meeting is on Monday at {h}:00 in room B.", "monday"),
      ("The planning meeting is on Wednesday at {h}:00 in room B.", "wednesday"),
      ("The planning meeting is on Friday at {h}:00 in room B.", "friday")], "Bring last month's figures."),
    ("score", "Rate the sentiment of the review.", ["very negative", "negative", "neutral", "positive", "very positive"],
     "Review {n} posted by {name}.",
     [("Terrible service, rude staff and the product broke on day one.", 0),
      ("Delivery took {d} days, which is about what I expected.", 2),
      ("Absolutely wonderful, fast delivery and great quality, I love it!", 4)], "Verified purchase."),
    ("score", "How urgent is the request?", ["none", "low", "medium", "high"], "Help-desk ticket {n} from {name}.",
     [("The whole office has no internet and customers cannot reach us right now.", 3),
      ("Please change my desktop wallpaper whenever you have time, no hurry.", 0),
      ("The shared printer prints slightly faded pages but still works.", 1)], "Logged at {h}:00."),
]


def synthetic(n, seed=7):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        t, instr, crit, ctx, evs, tail = TEMPLATES[i % len(TEMPLATES)]
        ev, label = evs[(i // len(TEMPLATES)) % len(evs)]
        f = {"n": 1000 + i, "name": rng.choice(NAMES), "amount": rng.randrange(2, 90) * 10,
             "d": rng.randrange(2, 28), "h": rng.randrange(8, 18)}
        ev = ev.format(**f)
        q = {"type": t, "instructions": instr}
        if crit is not None:
            q["criteria"] = crit
        out.append({"id": f"syn-{i:03d}", "lang": "en", "state": f"{ctx.format(**f)} {ev} {tail.format(**f)}",
                    "evidence": ev, "question": q, "label": label})
    return out


def extended(q):
    t = q["type"]
    if t == "choice":
        crit = dict(q["criteria"])
        crit[INSUFFICIENT] = INSUFFICIENT_TEXT
        return {"type": "choice", "instructions": q.get("instructions"), "criteria": crit}
    if t == "score":
        return {"type": "score", "instructions": q.get("instructions"),
                "criteria": list(q["criteria"]) + [f"{INSUFFICIENT}: {INSUFFICIENT_TEXT}"]}
    return {"type": "choice", "instructions": q.get("instructions"),
            "criteria": {"yes": "the statement is true", "no": "the statement is false", INSUFFICIENT: INSUFFICIENT_TEXT}}


def companion(q):
    instr = q.get("instructions")
    instr = instr if isinstance(instr, str) else json.dumps(instr)
    return {"type": "noul", "instructions": f"The state contains the information needed to answer: {instr}"}


def make(sources):
    rng = random.Random(11)
    items = []
    for src in sources:
        neutral = rng.choice(NEUTRAL)
        twin = src["state"].replace(src["evidence"], neutral, 1)
        assert twin != src["state"], src["id"]
        for missing, state in ((False, src["state"]), (True, twin)):
            sid = metrics.state_id(state)
            base = f"{src['id']}:{'twin' if missing else 'orig'}"
            common = {"state": state, "state_id": sid, "pair": src["id"], "missing": missing}
            items.append(dict(common, id=base + ":q", role="orig", question=src["question"],
                              label=None if missing else src["label"]))
            items.append(dict(common, id=base + ":ext", role="ext", question=extended(src["question"]), label=None))
            items.append(dict(common, id=base + ":comp", role="comp", question=companion(src["question"]), label=None))
    return items


def confidence(r):
    p = list(r["probs"].values())
    n = len(p)
    if r["type"] == "noul":
        return abs(2 * r["probs"]["true"] - 1)
    m = max(range(n), key=lambda i: p[i])
    if r["type"] == "choice":
        return 1.0 if n == 1 else (p[m] - 1 / n) / (1 - 1 / n)
    mad = sum(abs(i - (n - 1) / 2) for i in range(n)) / n
    return max(0.0, 1 - sum(p[i] * abs(i - m) for i in range(n)) / mad)


def score(items_path, results_path):
    items = {json.loads(l)["id"]: json.loads(l) for l in open(items_path) if l.strip()}
    res = {json.loads(l)["id"]: json.loads(l) for l in open(results_path) if l.strip()}
    det = {1: ([], []), 2: ([], []), 3: ([], []), 4: ([], [])}
    states = 0
    for iid, it in items.items():
        if it["role"] != "orig":
            continue
        base = iid[:-2]
        o, e, c = res.get(iid), res.get(base + ":ext"), res.get(base + ":comp")
        if not (o and e and c and o.get("probs") and e.get("probs") and c.get("probs")):
            continue
        states += 1
        k = 0 if it["missing"] else 1  # 0: positives (answer missing)
        ins = e["probs"].get(INSUFFICIENT, e["probs"].get(str(len(e["probs"]) - 1)))
        det[1][k].append(1 - confidence(o))
        det[2][k].append(ins)
        det[3][k].append(1 - c["probs"]["true"])
        det[4][k].append(1 - o["legal_mass"])
    names = {1: "1 - confidence", 2: "p(insufficient option)", 3: "1 - p(companion noul)", 4: "1 - legal mass"}
    print(f"abstain: {states} states")
    print("| detector | AUROC |\n|---|---|")
    best = 0
    for d in (1, 2, 3, 4):
        a = metrics.auroc(det[d][0], det[d][1])
        if d in (2, 3):
            best = max(best, a)
        print(f"| {d}. {names[d]} | {a:.3f} |")
    print("abstention needs no engine work" if best >= 0.9 else
          f"abstention: best explicit detector AUROC {best:.3f} < 0.9")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--fixtures", required=True)
    m.add_argument("--synthetic", type=int, default=140)
    m.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--items", required=True)
    s.add_argument("--results", required=True)
    a = ap.parse_args()
    if a.cmd == "make":
        src = [json.loads(l) for l in open(a.fixtures) if l.strip()] + synthetic(a.synthetic)
        items = make(src)
        with open(a.out, "w") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"abstain: {len(src)} sources, {len(items) // 3} states, {len(items)} questions -> {a.out}")
    else:
        score(a.items, a.results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
