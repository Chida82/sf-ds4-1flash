#!/usr/bin/env python3
"""Send a JSONL set of single-question decisions to the server and score them (change 820).

    run.py --base-url http://127.0.0.1:8002 --items FILE --mode sysone|gen|think|teacher
           [--limit N] [--rotate K] [--sf JSON] [--out results.jsonl] [--label TEXT]

sysone: POST /v1/systemone with "sf":{"debug":true} (merged with --sf). Consecutive
items of one state go in one request (questions are isolated, so this is the same
answer as one request per item and pays the state once); per-item latency is the
question's own ms plus its share of the state prefill.
gen/think/teacher: POST /v1/chat/completions with the 800 template's wording.
Standard library only.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics  # noqa: E402

SYSTEM = ("You are a decision function. Read the state and answer the question by "
          "choosing exactly one of the listed options.")


def load_items(path, limit=None):
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            it = json.loads(line)
            if "state_id" not in it:
                st = it["state"] if isinstance(it["state"], str) else json.dumps(it["state"], separators=(",", ":"))
                it["state_id"] = metrics.state_id(st)
            items.append(it)
            if limit and len(items) >= limit:
                break
    return items


def label_key(item):
    lab = item.get("label")
    if lab is None:
        return None
    if item["question"]["type"] == "noul":
        return "true" if lab in (True, "true") else "false"
    return str(lab)


def rotated(question, k):
    """Choice only: rotate option order by k. Names travel with options, so answers map back by name."""
    if question["type"] != "choice" or not k:
        return question
    keys = list(question["criteria"])
    k %= len(keys)
    keys = keys[k:] + keys[:k]
    q = dict(question)
    q["criteria"] = {key: question["criteria"][key] for key in keys}
    return q


def option_keys(question):
    t = question["type"]
    if t == "noul":
        return ["true", "false"]
    if t == "score":
        return [str(i) for i in range(len(question["criteria"]))]
    return list(question["criteria"])


def text_of(v):
    if v is None or isinstance(v, str):
        return v
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def template_prompt(state, question):
    """The user turn as the 800 template (version 1, T-C) writes it, for gen/think."""
    st = state if isinstance(state, str) else json.dumps(state, separators=(",", ":"), ensure_ascii=False)
    t = question["type"]
    lines = []
    if t == "choice":
        for i, (name, desc) in enumerate(question["criteria"].items()):
            d = text_of(desc)
            lines.append(f"{chr(65 + i)}. {name}: {d}" if d else f"{chr(65 + i)}. {name}")
    elif t == "noul":
        crit = question.get("criteria") or {}
        for i, (word, key) in enumerate((("Yes", "true"), ("No", "false"))):
            d = text_of(crit.get(key))
            lines.append(f"{chr(65 + i)}. {word}: {d}" if d else f"{chr(65 + i)}. {word}")
    else:
        for i, level in enumerate(question["criteria"]):
            lines.append(f"{i}. {text_of(level) or ''}")
    instr = text_of(question.get("instructions")) or ""
    return (f"State:\n{st}\n\nQuestion: {instr}\nOptions:\n" + "".join(l + "\n" for l in lines)
            + "Answer with the identifier only.")


def extract_symbol(reply, question):
    """First option symbol standing alone in the reply, as an option key; None when absent."""
    keys = option_keys(question)
    syms = [str(i) for i in range(len(keys))] if question["type"] == "score" else [chr(65 + i) for i in range(len(keys))]
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Z]|[0-9])(?![A-Za-z0-9])", reply or ""):
        if m.group(1) in syms:
            return keys[syms.index(m.group(1))]
    return None


def post(base, path, body, timeout=3600):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
            status = r.status
    except urllib.error.HTTPError as e:
        status, data = e.code, e.read().decode()
    return status, data, (time.monotonic() - t0) * 1e3


def run_sysone(base, items, rotate, sf_extra, deadline=None):
    out = []
    i = 0
    while i < len(items):
        if deadline and time.time() > deadline:
            print(f"run: deadline reached after {i} items", file=sys.stderr)
            break
        group = [items[i]]
        while (i + len(group) < len(items) and len(group) < 64
               and items[i + len(group)]["state_id"] == items[i]["state_id"]
               and items[i + len(group)]["state"] == items[i]["state"]):
            group.append(items[i + len(group)])
        i += len(group)
        sf = {"debug": True}
        sf.update(sf_extra)
        body = {"model": "deepseek-v4.1-flash", "state": group[0]["state"],
                "questions": {it["id"]: rotated(it["question"], rotate) for it in group}, "sf": sf}
        status, r, wall = post(base, "/v1/systemone", body)
        if status != 200:
            print(f"run: {group[0]['id']}: HTTP {status}: {str(r)[:300]}", file=sys.stderr)
            for it in group:
                out.append({"id": it["id"], "state_id": it["state_id"], "type": it["question"]["type"],
                            "label": label_key(it), "probs": {}, "error": status})
            continue
        sfr = r["sf"]
        share = sfr["prefill_ms"] / len(group)
        for it in group:
            a = r["answers"][it["id"]]
            q = sfr["questions"][it["id"]]
            t = it["question"]["type"]
            if t == "noul":
                probs = {"true": a["noul"], "false": 1 - a["noul"]}
            else:
                probs = a["probabilities"]
            keys = option_keys(it["question"])
            probs = {k: probs[k] for k in keys}  # original option order, whatever was sent
            out.append({"id": it["id"], "state_id": it["state_id"], "type": t, "label": label_key(it),
                        "probs": probs, "logits": {k: q["logits"][k] for k in keys},
                        "legal_mass": q["legal_mass"], "ms": q["ms"] + share,
                        "tokens": q["suffix_tokens"] + sfr["prefix_tokens"] / len(group),
                        "unstable": q.get("unstable", False), "temperature": q.get("temperature"),
                        "wall_ms": wall / len(group)})
        print(f"run: {i}/{len(items)}", file=sys.stderr, flush=True)
    return out


def chat_answer(base, item, rotate, effort, max_tokens, seed=None, temperature=0):
    q = rotated(item["question"], rotate)
    body = {"model": "deepseek-v4.1-flash",
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": template_prompt(item["state"], q)}],
            "temperature": temperature, "reasoning_effort": effort, "max_tokens": max_tokens}
    if seed is not None:
        body["seed"] = seed
    status, r, wall = post(base, "/v1/chat/completions", body)
    if status != 200:
        return None, "", wall, 0
    reply = r["choices"][0]["message"].get("content") or ""
    toks = r.get("usage", {}).get("total_tokens", 0)
    return extract_symbol(reply, q), reply, wall, toks


def run_chat(base, items, rotate, mode, deadline=None):
    out = []
    for n, it in enumerate(items, 1):
        if deadline and time.time() > deadline:
            print(f"run: deadline reached after {n - 1} items", file=sys.stderr)
            break
        keys = option_keys(it["question"])
        if mode == "gen":
            ans, reply, wall, toks = chat_answer(base, it, rotate, "none", 8)
        else:
            ans, reply, wall, toks = chat_answer(base, it, rotate, "high", 4096)
        rec = {"id": it["id"], "state_id": it["state_id"], "type": it["question"]["type"],
               "label": label_key(it), "answer": ans, "parse_failure": ans is None,
               "reply": reply[-200:], "ms": wall, "tokens": toks}
        if mode == "teacher":
            ans2, _, wall2, _ = chat_answer(base, it, rotate, "high", 4096, seed=1, temperature=0.7)
            rec["answer2"] = ans2
            rec["teacher_label"] = ans if ans is not None and ans == ans2 else None
            rec["ms"] += wall2
        rec["probs"] = {k: float(k == ans) for k in keys}
        out.append(rec)
        print(f"run: {n}/{len(items)} {mode} -> {ans}", file=sys.stderr, flush=True)
    return out


def fmt(x, nd=3):
    return "-" if x != x else f"{x:.{nd}f}"


def report(results, mode, label):
    rows = []
    for t in ("noul", "choice", "score", None):
        sel = [r for r in results if (t is None or r["type"] == t) and r.get("probs")]
        if not sel:
            continue
        s = metrics.summary(sel)
        rows.append((t or "all", s))
    print("| type | n | states | accuracy | 95% CI | NLL | Brier | ECE | mass mean | mass min | p50 ms | p95 ms | tokens |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t, s in rows:
        print(f"| {t} | {s['n']} | {s['states']} | {fmt(s['accuracy'])} | {fmt(s['ci95'][0])}-{fmt(s['ci95'][1])} | "
              f"{fmt(s['nll'])} | {fmt(s['brier'])} | {fmt(s['ece'])} | {fmt(s['mass_mean'], 4)} | {fmt(s['mass_min'], 4)} | "
              f"{fmt(s['p50_ms'], 0)} | {fmt(s['p95_ms'], 0)} | {fmt(s['tokens'], 0)} |")
    s = rows[-1][1]
    fails = sum(r.get("parse_failure", False) for r in results)
    print(f"\nrecord: | {label} | {mode} | {s['n']} | {fmt(s['accuracy'])} ({fmt(s['ci95'][0])}-{fmt(s['ci95'][1])}) | "
          f"{fmt(s['nll'])} | {fmt(s['brier'])} | {fmt(s['ece'])} | {fmt(s['mass_mean'], 4)} | {fmt(s['p50_ms'], 0)} | {fmt(s['p95_ms'], 0)} |"
          + (f" parse failures {fails}" if mode != "sysone" else ""))


# 830: three requests on one state, then the state extended by an appended note.
EXTENSION = ("\nInternal note appended later: the customer called again this morning, repeated the "
             "same request, confirmed the order number and the account details above, and asked to be "
             "contacted by email rather than by phone. No other information was given during the call, "
             "and the agent promised an answer within one business day.")


def run_repeat(base, items, scenario, n_states=20, deadline=None):
    """repeat: per state, requests 1-3 with the same question, then the extended state.
    extended: only the extended state (run on a server with --sysone-state-cache 0
    for the from-scratch reference)."""
    seen, out = set(), []
    for it in items:
        if it["state_id"] in seen or it["question"]["type"] == "score":
            continue
        if len(seen) == n_states or (deadline and time.time() > deadline):
            break
        seen.add(it["state_id"])
        sends = [("r1", it["state"]), ("r2", it["state"]), ("r3", it["state"])] if scenario == "repeat" else []
        sends.append(("ext", it["state"] + EXTENSION))
        for tag, state in sends:
            body = {"model": "deepseek-v4.1-flash", "state": state,
                    "questions": {"q": it["question"]}, "sf": {"debug": True}}
            status, r, wall = post(base, "/v1/systemone", body)
            if status != 200:
                print(f"run: {it['id']} {tag}: HTTP {status}", file=sys.stderr)
                continue
            q = r["sf"]["questions"]["q"]
            a = r["answers"]["q"]
            top = a.get("choice") if a["type"] == "choice" else ("true" if a["noul"] >= 0.5 else "false")
            out.append({"id": it["id"], "state_id": it["state_id"], "tag": tag, "wall_ms": wall,
                        "prefill_ms": r["sf"]["prefill_ms"], "prefix_tokens": r["sf"]["prefix_tokens"],
                        "state_cache": r["sf"].get("state_cache"), "top": top, "logits": q["logits"]})
        print(f"run: {len(seen)} states", file=sys.stderr, flush=True)
    return out


def run_live(base, items, n_states=20, deadline=None):
    """835: per state, one chat turn (thinking off), then up to three decisions on
    that conversation as a live state, then the same decisions with the
    conversation as a text state. Run on a server with --sysone-state-cache 0."""
    by_state = {}
    for it in items:
        if it["question"]["type"] != "score":
            by_state.setdefault(it["state_id"], []).append(it)
    out = []
    for sid, its in list(by_state.items())[:n_states]:
        if deadline and time.time() > deadline:
            break
        msgs = [{"role": "user", "content": "A customer wrote:\n" + its[0]["state"] + "\n\nDraft a short reply."}]
        status, c, _ = post(base, "/v1/chat/completions", {"model": "deepseek-v4.1-flash", "messages": msgs,
                            "temperature": 0, "reasoning_effort": "none", "max_tokens": 160})
        if status != 200:
            print(f"run: {sid} chat: HTTP {status}", file=sys.stderr)
            continue
        conv = msgs + [{"role": "assistant", "content": c["choices"][0]["message"]["content"]}]
        text = "\n\n".join(f"{m['role']}: {m['content']}" for m in conv)
        for layout in ("live", "text"):
            for it in its[:3]:
                body = {"model": "deepseek-v4.1-flash", "questions": {"q": it["question"]}, "sf": {"debug": True}}
                if layout == "live":
                    body["state"], body["sf"]["state"] = conv, "messages"
                else:
                    body["state"] = text
                status, r, wall = post(base, "/v1/systemone", body)
                if status != 200:
                    print(f"run: {it['id']} {layout}: HTTP {status}", file=sys.stderr)
                    continue
                out.append({"id": it["id"], "state_id": sid, "layout": layout, "wall_ms": wall,
                            "prefill_ms": r["sf"]["prefill_ms"], "prefix_tokens": r["sf"]["prefix_tokens"],
                            "reused_tokens": r["sf"].get("reused_tokens")})
        print(f"run: {sid} done", file=sys.stderr, flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8002")
    ap.add_argument("--items", required=True)
    ap.add_argument("--mode", choices=("sysone", "gen", "think", "teacher"), default="sysone")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--sf", default="{}", help="JSON merged into the request's sf object")
    ap.add_argument("--out")
    ap.add_argument("--label", default="")
    ap.add_argument("--deadline", type=float, help="unix time: send no new item after it, keep what was answered")
    ap.add_argument("--scenario", choices=("repeat", "extended", "live"),
                    help="830: per-state repeat and extension (needs --out); 'extended' sends only the extended states")
    a = ap.parse_args()
    items = load_items(a.items, a.limit)
    base = a.base_url.rstrip("/")
    if a.scenario:
        results = (run_live(base, items, deadline=a.deadline) if a.scenario == "live"
                   else run_repeat(base, items, a.scenario, deadline=a.deadline))
        with open(a.out, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
        return 0
    if a.mode == "sysone":
        results = run_sysone(base, items, a.rotate, json.loads(a.sf), a.deadline)
    else:
        results = run_chat(base, items, a.rotate, a.mode, a.deadline)
    if a.out:
        with open(a.out, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
    report(results, a.mode + (f" rotate {a.rotate}" if a.rotate else ""), a.label or os.path.basename(a.items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
