# Design

## Context

- The owner's teacher-forced work on DeepSeek V4 (ds4 `teacher-forced` branch,
  `snippets/ds4-runtime.patch`, `snippets/runtime_core.c`, Spec §4) established a
  decaying, phase-aware steering runtime: a cubic smoothstep from a strong start to a
  small residual, and a separate vector + schedule for the `<think>` phase, with the
  decay counter restarting at each phase change.
- This child has only a constant scale (`401`'s `--dir-steering-residual F`). msuiche's
  vector bakes alpha 0.5 constant; the decay and the phase split are not here yet.
- V4.1 reasons: it emits `<think>`/`</think>`. The engine already tracks generated
  tokens from the end of prefill.

## Goals / Non-Goals

**Goals:**
- A tunable dose: strong at the decision tokens, fading to a small residual.
- A separate schedule inside `<think>`.
- The disabled path (`decay-tokens 0`, no think file) bitwise identical to `401`.

**Non-Goals:**
- Building the think DIRECTION (conditional, only if `402` shows reasoning-phase
  leakage); an adaptive event-based decay (that is `405`); the measurement itself
  (`402`).

## Decisions

### D1. Smoothstep, re-calibrated, not ported
- **Choice.** Keep the cubic `3t^2 - 2t^3` shape. Set the start near V4.1's knee
  (grid ~0.3-0.7), the final small, decay-tokens on the order of the decision window,
  all swept and judged by `402`.
- **Rejected.** Porting the 0731 numbers (start -3, decay 30, final -0.1). msuiche's
  card forbids it: a different hook, and V4.1's alpha is non-monotone — 0.5 is the
  knee, 1.0 code-switches, 2.0 removes less. A -3 start would wreck the output.

### D2. Same vector, different schedule per phase; think vector optional
- **Choice.** Default to one direction with answer-phase and think-phase schedules.
  Add `--dir-steering-think-file` only when a think-specific direction is needed.
- **Rejected.** A mandatory second vector. The owner's preference is the simpler form;
  the second direction earns its place only against a measured think-phase leak (`402`).

### D3. Phase counter restarts at the phase boundary
- `generated = len - max(generation_start, phase_start)`, where `phase_start` is the
  index just after the last `<think>`/`</think>`. Without the restart, a long think
  block would run the answer out at its final scale from the first token.

### D4. Disabled path is `401` exactly
- `decay-tokens 0` makes `scale(t) = start`, the constant. No think file means no phase
  lookup. With scale 0, no tensor is allocated. So the no-op gate holds unchanged.

## Risks / Trade-offs

- **[Phase scan is O(n) per token]** → `ds4_session_in_think_at` walks the checkpoint
  each token (Spec §6.2). Negligible against the forward, but real; an incremental
  phase state is a later option, not needed now.
- **[Non-monotone alpha]** → a start above ~1 can remove *less* refusal and
  code-switch. The grid stays near the knee; the docs carry the warning.
- **[Start/decay are per-model, per-quant]** → the values hold for this checkpoint at
  this hook only. `402` re-runs the sweep; the sidecar records what was used.
