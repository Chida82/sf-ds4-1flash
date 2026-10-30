# Proposal

## Why

The steering scale the V4.1 graph reads lives in each session (`s->ds41_graph.residual_scale`, `residual_scale2`, `closure_scale`). `ds41_steering_apply_gates` (`ds4.c:28473`) recomputes it every token, but always from the engine's profile, and `ds4_session_create` arms it in every session the engine opens. No caller can say "this session runs unsteered" while the profile stays loaded. The server needs exactly that to let each request choose (`640`).

The batch decision has the same engine-wide shape. `ds4.c:33429` declines the native batched decode for **every** session as soon as the profile has a gate or a schedule, and the shipped candor profile has both. With a profile loaded but unused, unsteered requests would still lose batching.

This change adds the switch in the engine, where the scale lives, so the guarantee does not depend on each frontend remembering it.

## What Changes

- **A per-session steering switch:**
  - `ds4_session_set_steering(ds4_session *s, bool on)` and `ds4_session_steering(const ds4_session *s)`.
  - Turning it on when the engine has no profile fails with an error.
  - A new session starts **on** when the engine loaded a profile, so the CLI and eval keep today's behaviour with no change. The server sets it per request.
- **Off is the unsteered model, bitwise.**
  - With the switch off, the three scales are zero for every token, and the phase tracking in `ds41_steering_on_prompt` / `ds41_steering_on_decode` is skipped.
  - The fold and closure routes then dispatch nothing and the HC block input keeps its fused fast paths (`ds41_hc_mix`).
  - Logits, KV and Engram history match an engine opened without the profile.
- **No state crosses the switch.** Changing the switch on a session that holds live state drops that state (tokens, KV, logits) before the next evaluation. The next sync re-prefills from zero, so no prefix computed under one setting is ever extended under the other. The server's routing (`640`) avoids paying for this, but correctness does not depend on it.
- **Batching is decided per item.** The native batched decode is declined when the items differ in steering, or when a steered item runs under a gated or scheduled profile. A batch of unsteered sessions is batched even with such a profile loaded. Steered sessions keep the path they use today, because one batched forward applies a single scale to every row.
- **Persistence follows the session.**
  - `ds41_steering_refuses_persistence` already reads the session's scales, so a switched-off session saves and loads payloads normally.
  - A steered session still refuses; `650` lifts that for the server's segregated store.
  - The check is restated to read the switch instead of inferring it from the scales, so a gated slot that happens to be at zero for this token does not count as unsteered.
- **Tests:**
  - **Model-backed**, in the style of `make test-deepseek41-decode-switch`:
    - profile loaded with the session off, against no profile: 65 decoded tokens, logits, KV and Engram history compared bitwise;
    - session on, against today's profile run: bitwise;
    - a session switched after a prefill re-prefills, and its output equals a fresh session's.
  - **Model-less:** the switch's error without a profile, and the batch decision for mixed items.

Non-goals:
- No frontend change in this change.
- No new profile semantics.
- No TP frame change: under TP the switch is left at its default (`640` refuses per-request steering with TP).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `directional-steering`:
  - adds "Per-session steering switch" (default from the profile, off is bitwise unsteered, switching drops live state);
  - changes "Per-slot reasoning-phase gate", scenario "Gated sessions do not share a batch": the decline applies to steered items, not to every session of a profiled engine;
  - restates "Steering and persistent state" to key on the session switch.

## Impact

- **Code:** `ds4.c` (session field, gates, prompt/decode hooks, batch decision, persistence check), `ds4.h` (two functions). No frontend edits.
- **Speed:** none claimed. Steered and unsteered decode run the same kernels as today. The only scheduling change is that unsteered sessions under a loaded profile batch again, which matters only for the server with `--batched-sessions` > 1.
- **Order:** third. It needs `620`'s single steering source, and `640` and `650` build on it.
