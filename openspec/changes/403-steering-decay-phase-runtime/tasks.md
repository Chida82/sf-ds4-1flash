# Tasks

Depends on `401` (residual hook) and `400`. The sweep (3.2) needs the converted
msuiche vector and shares the model lock; `402`'s harness is the judge.

**Gate (2026-10-13): do not start until `402` task 7.4 has measured flat-scale drift on
long outputs.** 401's efficacy screen put the working window at ~4-8 on the residual
site (0.5 is a no-op there) and found benign output coherent through scale 8 at 90
tokens; whether a flat 4-8 scale distorts 512-token outputs is unmeasured. If it does
not, this change solves no measured problem and is archived without code; if it does,
that result is its baseline and its acceptance criterion.

## 1. Smoothstep schedule

- [ ] 1.1 `directional_steering_residual_scale_at(start, decay_tokens, final, generated)`
  in `ds4.c`: cubic `start + (final-start)*(3t^2 - 2t^3)`, `t = generated/decay_tokens`,
  clamped to `[0,1]`; `decay_tokens == 0` returns `start`. Verify a self-check on the
  endpoints and the monotone middle (reuse the `STEERING_SELF_CHECK` shape from
  `runtime_core.c`).
- [ ] 1.2 `--dir-steering-residual-decay-tokens N`, `--dir-steering-residual-decay-final F`
  in CLI/server/bench/help, with the `ds4_engine_options` fields. Save
  `directional_steering_generation_start` in the session at prefill end. Verify `--help`
  lists them and `generated` is 0 on the first decoded token.

## 2. Think phase

- [ ] 2.1 `ds4_session_in_think_at(tokens, len, think_id, end_id, &phase_start)`:
  toggles on `<think>`/`</think>`, returns whether the next token is inside think and
  the index where the phase began. Verify a 100-think-token case, then `</think>`,
  starts the answer phase fresh (self-check).
- [ ] 2.2 Per-step selection: inside think use the think vector/scale, else the answer
  vector/scale, with `generated = len - max(generation_start, phase_start)`. Load the
  optional `--dir-steering-think-file` on CPU and Metal. Verify the answer schedule is
  not exhausted after a long think block.
- [ ] 2.3 `--dir-steering-think-file FILE`, `--dir-steering-think-residual F`,
  `--dir-steering-think-decay-tokens N`, `--dir-steering-think-decay-final F` in the
  frontends. Classify any disable switch in `ds4_env.def`. Verify `make env-check` and
  `--help`.

## 3. Verify

- [ ] 3.1 No-op gate: `--dir-steering-residual-decay-tokens 0` with no think file
  reproduces `401` exactly; scale 0 is bitwise identical. Verify
  `make test-deepseek41-decode-switch` on the relevant switch.
- [ ] 3.2 Calibration sweep (needs the vector; shares the lock): start in ~{4,6,8}
  (the measured residual-site window; the earlier {0.3,0.5,0.7} were msuiche-site
  values and are no-ops here), decay-tokens in ~{10,20,40}, final in ~{0,1,2}, at
  `--temp 0.1` fixed seed,
  scored by `402` on the A axis (removal) and B/C (collateral). Verify the knee is kept
  (smallest start that removes refusals without code-switching), NOT the extreme; record
  the chosen values and that the 0731 numbers were not used.

## 4. Docs

- [ ] 4.1 `dir-steering/README.md`: the schedule, the phase split, the think flags, and
  the V4.1 scale note (residual-site window ~4-8; msuiche's 0.5 is a no-op there; do
  not port the 0731 alpha). Verify no doc reuses the 0731 start/decay, or 0.5, as a
  V4.1 default.
- [ ] 4.2 Provenance in `docs/upstream-prs.md`/registry (the `teacher-forced` branch of
  ds4): not in source comments.

## 5. Integration

- [ ] 5.1 `make test` (incl. env-check),
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` on the disabled
  path token-identical, `openspec validate 403-steering-decay-phase-runtime --strict`.
  No commit or push without a request.
