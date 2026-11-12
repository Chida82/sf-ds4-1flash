# Design

Depends on `820` (calibration, bench) and `860` (the think path). If `860`
was not built (its own gate said stop), this change is not started.

## Request option

```json
"sf": {"escalate": {"below": 0.8, "think": 256}}
```

- `below`: 0-1. Compared with the **calibrated** top probability (`p[top]`
  after the type's temperature from `--sysone-calibration`); without a
  calibration file, the raw one, and the `sf` object says
  `"calibrated": false`.
- `think`: the `860` budget N, 1..`860`'s maximum.
- Invalid values: 422 with `loc ["body","sf","escalate", field]`.
- `noul`: the top probability is `max(p, 1 − p)`.

## Flow in `sysone_job`

1. Plain decision as today (all questions, one prefill, branches).
2. Collect the indices with top probability `< below`. None: done.
3. Run `860`'s think path for those questions only, on the same state, as one
   `860` request would (its own state prefix with the effort line: a second
   prefill of the state; `830`'s cache keys it separately).
4. Replace those answers; keep the plain answer in the `sf` object.

The response's standard fields are the final answers. With `sf` present,
per escalated question: `"escalated": true`, `"plain": {...}` (the plain
answer fields), `"think_tokens"`, `"think_closed"`. `usage.output_tokens` is
the sum of thinking tokens (as `860`).

Cost note for the docs: an escalation costs a second state prefill (the think
prefix differs) plus N + suffix tokens per escalated question.

## Server default

`--sysone-escalate C:N` sets the option for requests without
`sf.escalate`; a request's own option wins; `"escalate": null` turns it off
for one request.

## Bench sweep

`sysone-bench/escalate_sweep.py`: on the `typed-decisions` test split (first
200 items) and `fixtures-it.jsonl`, run `run.py --mode sysone --sf` with
`below` in {0, 0.6, 0.7, 0.8, 0.9, 0.95} and `think` fixed at the `N` that
`860`'s trajectory run chose. Report per `below`: accuracy (interval),
escalated share, mean and p95 ms per decision.

Default choice: the smallest `below` that reaches 90% of the accuracy gain of
`below = 1.0` (all escalated, which is `860`'s plain think run; reuse its
figure). Write it in `docs/SERVER.md` as the suggested value; the flag stays
off by default.

## Risks

- Escalation is only as good as calibration: with a badly calibrated type the
  wrong questions escalate. The sweep shows it as a poor gain curve.
- Determinism: the escalated answer depends on the think path's argmax decode,
  deterministic on the same build (`860` tests it).
