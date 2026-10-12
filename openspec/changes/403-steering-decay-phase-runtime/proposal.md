# Proposal

## Why

msuiche's vector bakes a single constant alpha (0.5). A constant strong edit is the
wrong dose over a whole answer: the refuse-or-answer decision is taken in the first
generated tokens; after that the model follows the trajectory it entered, and a
sustained push drifts the text (the owner's teacher-forced work on DeepSeek V4 found
this, and fixed it with a decaying schedule). The schedule and the think/non-think
split from that work are not yet in this child. This change ports them onto the
residual hook of `401`, so the dose is strong at the start and fades to a small
residual, with its own schedule inside `<think>`.

## What Changes

- **Smoothstep decay.** `scale(t) = start + (final - start) * (3t^2 - 2t^3)`,
  `t = generated / decay_tokens` (cubic; linear and quadratic ramps were tried and
  discarded upstream). `--dir-steering-residual-decay-tokens N` and
  `--dir-steering-residual-decay-final F`. With `N = 0` the scale is constant (the
  `401` behavior), so the disabled path is unchanged.
- **Think phase.** `--dir-steering-think-file FILE`, `--dir-steering-think-residual F`,
  `--dir-steering-think-decay-tokens N`, `--dir-steering-think-decay-final F`. The
  engine toggles phase on `<think>`/`</think>` and applies the think schedule inside a
  think block, the answer schedule outside. The decay counter restarts at each phase
  change, so a long reasoning block does not exhaust the answer schedule.
- **Re-calibrated for V4.1, not ported.** The DeepSeek V4-0731 numbers (start -3,
  decay 30, final -0.1, at a different hook) are NOT reused: msuiche's card forbids
  porting that alpha and shows V4.1 is sharply non-monotone (0.5 is the knee, 2.0
  regresses). The decay shape holds; the start sits near the knee (grid ~0.3-0.7),
  measured by `402`.
- **Think vector is optional.** By default the same vector runs with a different
  schedule per phase. A separate think direction is added only if `402` measures
  refusal leaking through the reasoning phase.

## Capabilities

### Modified Capabilities
- `directional-steering`: the residual scale gains a per-phase smoothstep decay and an
  optional separate think vector; with `decay-tokens 0` and no think file it reduces to
  `401`'s constant scale.

## Impact

- `ds4.c`: `directional_steering_residual_scale_at` (smoothstep),
  `ds4_session_in_think_at` (phase + phase-start index), the per-step vector/scale
  selection, the second (think) vector load on CPU and Metal, and
  `directional_steering_generation_start` saved in the session at prefill end.
- `ds4_cli.c`, `ds4_server.c`, `ds4_bench.c`, `ds4_help.c`: the six flags; `ffn`/`attn`
  decay variants only if trivial.
- `ds4_env.def`: any disable switch classified.
- `dir-steering/README.md`, `docs/`: the schedule, the phase split, and the V4.1
  calibration warning.
- `docs/upstream-prs.md` / registry: provenance (the owner's `teacher-forced` branch of
  ds4, `snippets/ds4-runtime.patch`); not in source comments.
- Depends on `401` (residual hook) and `400`. Measured by `402`.
