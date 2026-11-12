#!/usr/bin/env python3
"""Live check of POST /v1/systemone (change 810) against a running server.

Starts nothing. Run it on a server started WITHOUT --kv-disk-dir: with a disk
cache the second chat could resume from a checkpoint, and a different prefill
schedule gives different, equally valid bits.

    ./sf-ds4-1flash-server --ssd-streaming --ctx 32768 &
    python3 tests/test_sysone_http.py --base-url http://127.0.0.1:8002
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

FAILURES = []


def check(ok, name):
    print(f"sysone-http: {name} {'OK' if ok else 'FAIL'}", flush=True)
    if not ok:
        FAILURES.append(name)


def post(base, path, body, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, text


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode())


STATE = "My package arrived broken and I want my money back."
QUESTIONS = {
    "intent": {"type": "choice", "criteria": {"refund_request": None, "shipping_question": None, "praise": None}},
    "satisfied": {"type": "noul", "instructions": "The customer is satisfied."},
    "sentiment": {"type": "score", "instructions": "Rate the sentiment of the message.",
                  "criteria": ["very negative", "negative", "neutral", "positive", "very positive"]},
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8002")
    base = ap.parse_args().base_url.rstrip("/")

    models = get(base, "/v1/models")
    check(isinstance(models.get("data"), list) and isinstance(models.get("models"), list), "models: data and models arrays")
    name = models["models"][0]["name"]
    check(set(models["models"][0]) == {"name", "description", "release_date"}, "models: Jev entry fields")

    status, r = post(base, "/v1/systemone", {"model": "jev-latest", "state": STATE, "questions": QUESTIONS})
    check(status == 200, "decision: status 200")
    if status != 200:
        print(r)
        return 1
    check(list(r) == ["model", "answers", "usage"], "decision: top-level keys exactly model, answers, usage")
    check(r["model"] == name, "decision: model is the local id")
    check(list(r["answers"]) == list(QUESTIONS), "decision: answers in request order")
    a = r["answers"]
    check(a["intent"]["type"] == "choice" and a["intent"]["choice"] == "refund_request", "choice: refund_request")
    check(set(a["intent"]) == {"type", "choice", "confidence", "probabilities"}, "choice: fields")
    check(abs(sum(a["intent"]["probabilities"].values()) - 1) < 1e-6, "choice: probabilities sum to 1")
    check(set(a["satisfied"]) == {"type", "noul"} and a["satisfied"]["noul"] < 0.5, "noul: fields and value < 0.5")
    s = a["sentiment"]
    check(set(s) == {"type", "score", "confidence", "legend", "probabilities"}, "score: fields")
    check(list(s["legend"]) == ["0", "1", "2", "3", "4"] and s["legend"]["0"] == "very negative", "score: legend")
    check(abs(sum(s["probabilities"].values()) - 1) < 1e-6, "score: probabilities sum to 1")
    check(isinstance(s["score"], (int, float)) and 0 <= s["score"] <= 4, "score: value in range")
    check(r["usage"]["output_tokens"] == 0 and r["usage"]["input_tokens"] > 0, "usage: output_tokens 0")

    status, r = post(base, "/v1/systemone", {"model": name, "state": {"ticket": STATE, "tier": "gold"},
                                             "questions": {"q": QUESTIONS["intent"]}, "sf": {"debug": True}})
    check(status == 200 and "sf" in r and "logits" in r["sf"]["questions"]["q"], "structured state and sf.debug")
    if status == 200:
        print(f"sysone-http: sf {json.dumps(r['sf'])}")

    errors = [
        ("body not JSON", None, b"not json", 400),
        ("missing criteria", {"model": "m", "state": "s", "questions": {"c": {"type": "choice"}}}, None, 422),
        ("box", {"model": "m", "state": "s", "questions": {"b": {"type": "box"}}}, None, 422),
        ("assets", {"model": "m", "state": "s", "assets": {}, "questions": {"n": {"type": "noul"}}}, None, 422),
        ("27 options", {"model": "m", "state": "s", "questions": {"c": {"type": "choice",
            "criteria": {f"o{i}": None for i in range(27)}}}}, None, 422),
        ("over the context", {"model": "m", "state": "word " * 40000, "questions": {"n": {"type": "noul"}}}, None, 400),
    ]
    for label, body, raw, want in errors:
        status, r = post(base, "/v1/systemone", body, raw)
        ok = status == want
        if want == 422:
            ok = ok and isinstance(r, dict) and isinstance(r.get("detail"), list) and {"loc", "msg", "type"} <= set(r["detail"][0])
        if label == "missing criteria":
            ok = ok and r["detail"][0]["loc"][-2:] == ["c", "criteria"]
        if label == "over the context":
            ok = ok and "max_tokens_exceeded" in json.dumps(r)
        check(ok, f"error: {label} -> {want}")

    chat = {"model": name, "messages": [{"role": "user", "content": "Name three primary colors."}],
            "temperature": 0, "reasoning_effort": "none", "max_tokens": 24}
    status1, c1 = post(base, "/v1/chat/completions", chat)
    post(base, "/v1/systemone", {"model": name, "state": STATE, "questions": QUESTIONS})
    status2, c2 = post(base, "/v1/chat/completions", chat)
    t1 = c1["choices"][0]["message"]["content"] if status1 == 200 else None
    t2 = c2["choices"][0]["message"]["content"] if status2 == 200 else None
    check(t1 is not None and t1 == t2, "chat, decision, chat: equal answers")

    # 830: state cache and chat preservation
    one = {"model": name, "state": STATE + " Order 4471.", "questions": {"q": QUESTIONS["intent"]}, "sf": {"debug": True}}
    s1, r1 = post(base, "/v1/systemone", one)
    s2, r2 = post(base, "/v1/systemone", one)
    if s1 == 200 and s2 == 200 and r2["sf"].get("state_cache"):
        check(r2["sf"]["state_cache"] == "hit" and r2["sf"]["prefill_ms"] < 100, "state cache: repeat is a hit with prefill under 100 ms")
        check(r1["sf"]["questions"]["q"]["logits"] == r2["sf"]["questions"]["q"]["logits"]
              and r1["answers"] == r2["answers"], "state cache: hit answers equal the creating request")
        print(f"sysone-http: repeat prefill_ms {r1['sf']['prefill_ms']} -> {r2['sf']['prefill_ms']}")
        ext = dict(one, state=one["state"] + " The box was also wet and the manual is missing.")
        s3, r3 = post(base, "/v1/systemone", ext)
        check(s3 == 200 and r3["sf"]["state_cache"] == "extend", "state cache: appended state is an extension")
        if s3 == 200:
            print(f"sysone-http: extend prefill_ms {r3['sf']['prefill_ms']}")
    else:
        check(s1 == 200 and s2 == 200, "state cache off: requests still answered")

    turn1 = {"model": name, "messages": [{"role": "user", "content": "Name three primary colors."}],
             "temperature": 0, "reasoning_effort": "none", "max_tokens": 24}
    st, a1 = post(base, "/v1/chat/completions", turn1)
    post(base, "/v1/systemone", {"model": name, "state": STATE, "questions": QUESTIONS})
    turn2 = dict(turn1, messages=turn1["messages"] + [
        {"role": "assistant", "content": a1["choices"][0]["message"]["content"]},
        {"role": "user", "content": "And three secondary colors?"}])
    st2, a2 = post(base, "/v1/chat/completions", turn2)
    cached = a2.get("usage", {}).get("prompt_tokens_details", {}).get("cached_tokens", 0) if st2 == 200 else 0
    prompt2 = a2.get("usage", {}).get("prompt_tokens", 0) if st2 == 200 else 0
    print(f"sysone-http: chat continuation after a decision: prompt {prompt2}, cached {cached}")
    check(st == 200 and st2 == 200 and cached >= a1["usage"]["prompt_tokens"],
          "chat, decision, chat continuation: the chat prefix survives the decision")

    # 835: the conversation the slot just generated, as the state (thinking off)
    msgs = [{"role": "user", "content": "In two sentences, why is the sky blue?"}]
    status, c = post(base, "/v1/chat/completions", {"model": name, "messages": msgs, "temperature": 0,
                                                    "reasoning_effort": "none", "max_tokens": 200})
    if status == 200:
        conv = msgs + [{"role": "assistant", "content": c["choices"][0]["message"]["content"]}]
        live = {"model": name, "state": conv, "questions": QUESTIONS, "sf": {"state": "messages", "debug": True}}
        s1, d1 = post(base, "/v1/systemone", live)
        s2, d2 = post(base, "/v1/systemone", live)
        ok = s1 == 200 and s2 == 200
        check(ok and d1["sf"]["layout"] == "live" and d1["sf"]["reused_tokens"] >= c["usage"]["prompt_tokens"],
              "live state: reused_tokens covers the chat prompt")
        check(ok and d1["sf"]["prefill_ms"] < 500, "live state: state prefill under 0.5 s")
        check(ok and all(d1["sf"]["questions"][k]["logits"] == d2["sf"]["questions"][k]["logits"] for k in QUESTIONS),
              "live state: three questions twice, bitwise equal")
        s3, c3 = post(base, "/v1/chat/completions", {"model": name, "temperature": 0, "reasoning_effort": "none",
                      "max_tokens": 8, "messages": conv + [{"role": "user", "content": "And at sunset?"}]})
        check(s3 == 200 and c3["usage"]["prompt_tokens_details"]["cached_tokens"] >= c["usage"]["total_tokens"] - 1,
              "live state: the next chat turn prefills only its new tokens")
    status, r = post(base, "/v1/systemone", {"model": name, "state": [{"role": "tool", "content": "x"}],
                                             "questions": QUESTIONS, "sf": {"state": "messages"}})
    check(status == 422 and r["detail"][0]["loc"][-1] == "role", "live state: tool role -> 422")

    print(f"sysone-http: {'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all checks passed'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
