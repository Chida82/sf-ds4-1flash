# Live run (2026-11-11, for the PR text)

Server: `./sf-ds4-1flash-server --ssd-streaming --ctx 32768`, no `--kv-disk-dir`. TypeSafe SDK: not installed (`import typesafe` fails), task 3.3 skipped.

```text
sysone-http: models: data and models arrays OK
sysone-http: models: Jev entry fields OK
sysone-http: decision: status 200 OK
sysone-http: decision: top-level keys exactly model, answers, usage OK
sysone-http: decision: model is the local id OK
sysone-http: decision: answers in request order OK
sysone-http: choice: refund_request OK
sysone-http: choice: fields OK
sysone-http: choice: probabilities sum to 1 OK
sysone-http: noul: fields and value < 0.5 OK
sysone-http: score: fields OK
sysone-http: score: legend OK
sysone-http: score: probabilities sum to 1 OK
sysone-http: score: value in range OK
sysone-http: usage: output_tokens 0 OK
sysone-http: structured state and sf.debug OK
sysone-http: sf {"template_version": 1, "prefix_tokens": 48, "prefill_ms": 1727.8, "questions": {"q": {"suffix_tokens": 30, "ms": 942.1, "legal_mass": 0.99985, "logits": {"refund_request": 28.7820511, "shipping_question": 18.9478989, "praise": 16.7199268}}}}
sysone-http: error: body not JSON -> 400 OK
sysone-http: error: missing criteria -> 422 OK
sysone-http: error: box -> 422 OK
sysone-http: error: assets -> 422 OK
sysone-http: error: 27 options -> 422 OK
sysone-http: error: over the context -> 400 OK
sysone-http: chat, decision, chat: equal answers OK
sysone-http: all checks passed
```
