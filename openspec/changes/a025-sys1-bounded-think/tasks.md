# Tasks

Start only if `sysone-bench/record.md` states a System One gap above 5 points
on at least one question family; otherwise write that sentence in
`docs/system-one.md` and archive this change unimplemented.

## 0. Trajectory

- [ ] 0.1 `tests/test_sysone --think-trajectory` as in the design (probe every 32 tokens through a snapshot).
- [ ] 0.2 Check on fixture 1 that the probes do not change the reasoning: the token sequence with probes equals the sequence of a run with probes disabled.
- [ ] 0.3 Run on the 12 fixtures, then on 200 bench items. Curve, forced-close legal mass and stabilisation histogram in `sysone-bench/record.md`. Apply the go/no-go rule.

## 1. Option

- [ ] 1.1 Move the loop into `sf_sysone.c` (`sf_sysone_think_answer`), ids from the assistant-prefix trick, the thinking state prefix.
- [ ] 1.2 Server: `sf.think_tokens`, `sf.think_effort`, validation, `usage.output_tokens`, `sf` response fields; unit tests.
- [ ] 1.3 Model-backed checks: N = 0 bitwise equal to `800`; determinism at N = 64; overflow refusal.

## 2. Curve

- [ ] 2.1 The confirming HTTP run at the chosen N and at N = 0; rows in `sysone-bench/record.md`.
- [ ] 2.2 Decide by the rule. On failure remove the option, keep the record.

## 3. Think once (only if `a015` was kept and section 2 passed)

- [ ] 3.1 The stage-2 prompt and snapshot point; `sf.think_scope`: `"question"` (default) or `"request"`.
- [ ] 3.2 Bench against per-question thinking; decide; record.

## 4. Docs

- [ ] 4.1 `docs/SERVER.md`: the options, the cost per thinking token, determinism.
- [ ] 4.2 `docs/system-one.md`: approach G result and the curve.
