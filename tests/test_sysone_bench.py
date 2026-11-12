#!/usr/bin/env python3
"""Unit tests of the System One bench metrics and helpers (change 820). Stdlib only."""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sysone-bench"))
import fit  # noqa: E402
import metrics  # noqa: E402
import run  # noqa: E402

FAIL = []


def check(ok, name):
    print(f"sysone-bench: {name} {'ok' if ok else 'FAIL'}")
    if not ok:
        FAIL.append(name)


def item(probs, label, sid="s"):
    return {"probs": probs, "label": label, "state_id": sid}


perfect = [item({"a": 1.0, "b": 0.0}, "a", str(i)) for i in range(10)]
check(metrics.accuracy(perfect) == 1 and metrics.brier(perfect) == 0 and metrics.ece(perfect) == 0
      and metrics.nll(perfect) == 0, "perfect predictor")

uniform = [item({"a": 0.5, "b": 0.5}, "b", str(i)) for i in range(10)]
check(metrics.accuracy(uniform) == 0 and abs(metrics.brier(uniform) - 0.5) < 1e-12
      and abs(metrics.nll(uniform) - math.log(2)) < 1e-12 and abs(metrics.ece(uniform) - 0.5) < 1e-12,
      "uniform predictor (ties to the first option)")

# known ECE: 4 items at confidence 0.8 (bin 8), 3 right -> |0.75-0.8|; 2 at 0.95 (bin 9), 1 right -> |0.5-0.95|
known = ([item({"a": 0.8, "b": 0.2}, "a")] * 3 + [item({"a": 0.8, "b": 0.2}, "b")]
         + [item({"a": 0.95, "b": 0.05}, "a"), item({"a": 0.95, "b": 0.05}, "b")])
check(abs(metrics.ece(known) - (4 / 6 * 0.05 + 2 / 6 * 0.45)) < 1e-12, "known ECE")

check(abs(metrics.percentile([1, 2, 3, 4], 0.5) - 2.5) < 1e-12, "percentile interpolates")
check(metrics.auroc([0.9, 0.8], [0.1, 0.8]) == 0.875, "AUROC with a tie")

two_states = [item({"a": 1, "b": 0}, "a", "A"), item({"a": 1, "b": 0}, "a", "A"),
              item({"a": 1, "b": 0}, "b", "B"), item({"a": 1, "b": 0}, "b", "B")]
accs = metrics.bootstrap_accuracy(two_states, n=500, samples=True)
check(set(accs) <= {0.0, 0.5, 1.0} and len(set(accs)) == 3, "bootstrap moves a state's items together")

q = {"type": "choice", "criteria": {"x": None, "y": "why", "z": None}}
r1 = run.rotated(q, 1)
check(list(r1["criteria"]) == ["y", "z", "x"] and r1["criteria"]["y"] == "why"
      and list(run.rotated(r1, 2)["criteria"]) == ["x", "y", "z"], "rotation round-trip")
check(run.rotated({"type": "score", "criteria": [1, 2]}, 1)["criteria"] == [1, 2], "score is never rotated")

score_q = {"type": "score", "criteria": ["lo", "mid", "hi"]}
noul_q = {"type": "noul"}
cases = [("B", q, "y"), ("The answer is C.", q, "z"), ("**A**", q, "x"), ("2", score_q, "2"),
         ("B. No", noul_q, "false"), ("I cannot tell", q, None)]
check(all(run.extract_symbol(reply, qq) == want for reply, qq, want in cases), "gen symbol extractor on six replies")

rng = random.Random(3)
rows = []
for i in range(400):
    true_logits = [rng.gauss(0, 3) for _ in range(4)]
    p = metrics.softmax(true_logits)  # the model's raw probabilities are these at T = 1
    u, acc, lab = rng.random(), 0, 0
    q2 = metrics.softmax(true_logits, 2.0)  # labels drawn at T = 2: the right temperature is 2
    for k, pk in enumerate(q2):
        acc += pk
        if u <= acc:
            lab = k
            break
    rows.append({"id": f"i{i}", "type": "choice", "label": str(lab),
                 "logits": {str(k): true_logits[k] for k in range(4)}, "probs": dict(zip(map(str, range(4)), p))})
t = fit.fit_type(rows)
check(1.6 <= t <= 2.5, f"fit recovers T = 2 (got {t:.2f})")

# 915: headroom parser. Two requests: the first swept (2 layers), the second token by token.
import headroom  # noqa: E402
log = headroom.parse_log("""ds4: gpu busy accum 100.0 ms over 64 cbs
ds4: V4.1 prefill layer=0 pos=0 rows=300 encoder_resident=0 map=10.000 engram=0.010 encode=1.000 drain=50.000 seed=0.500 ms
ds4: V4.1 prefill layer=1 pos=0 rows=300 encoder_resident=0 map=5.500 engram=0.010 encode=1.000 drain=40.000 seed=0.500 ms
ds4-server: systemone slot 0: state 300 tokens (miss), 2 questions, 900 ms, min legal mass 0.9990, chat state none
ds4-server: systemone slot 0: state 40 tokens (miss), 1 questions, 500 ms, min legal mass 0.9990, chat state none
ds4: gpu busy accum 250.5 ms over 128 cbs
ds4:   streaming expert timing total selected_calls=9 read_avg=1.000 ms split_layers=200 resident_experts_avg=5.00 missing_load_avg=0.617 ms missing_slot_avg=0.000 ms
""".splitlines())
items = [{"state_id": "a", "wall_ms": 450.0}, {"state_id": "a", "wall_ms": 450.0}, {"state_id": "b", "wall_ms": 500.0}]
s = headroom.summarize(log, [("r", items)])
r0 = s["rows"][0]
check(r0["requests"] == 2 and r0["wall_ms"] == 1400 and r0["sweep_wait_ms"] == 15.5 and r0["sweep_drain_ms"] == 90
      and r0["swept_requests"] == 1 and abs(s["decode_wait_ms"] - 123.4) < 1e-9 and s["split_layers"] == 200
      and s["gpu_ms"] == 250.5, "headroom parser sums")

print(f"sysone-bench: {'FAILED ' + ', '.join(FAIL) if FAIL else 'all tests passed'}")
sys.exit(1 if FAIL else 0)
