# Design

## Context

After `620`, the only steering source is the profile, which `ds41_steering_profile_open` loads into the engine's slot fields. Per session:

- `ds4_session_create` (`ds4.c:31880-31915`) uploads the slot directions to the session's V4.1 graph and arms `residual_scale`/`residual_scale2` from the engine. The closure matrix is uploaded too; its scale is set per token.
- `ds41_steering_on_prompt` / `ds41_steering_on_decode` (`ds4.c:28543-28566`) run only when the profile has a gate or a schedule (`ds41_steering_gated`, `ds41_steering_scheduled`), and call `ds41_steering_apply_gates` (`ds4.c:28473`). That function computes the three per-token scales from the engine's values and the session's phase.
- A profile with neither gates nor schedule never comes back to `apply_gates`: its constant scales are the ones set at creation.
- The graph routes test `ds41_steering_active` / `ds41_steering2_active` / the closure scale. At zero they dispatch nothing and `ds41_hc_mix` keeps the fused HC paths, which is what makes "off" bitwise unsteered.
- `ds4_sessions_batch_supported` (`ds4.c:33420-33433`) declines the native batch for the whole engine when a gate or schedule exists.
- `ds41_steering_refuses_persistence` (`ds4.c:28952`) refuses when either slot scale is nonzero on the session's graph.
- `ds4_session_invalidate` (`ds4.c:33736`) clears the checkpoint and resets the V4.1 graph, and tells TP workers.

## Goals / Non-Goals

**Goals:**
- One session flag that every steering decision reads: the scales, the phase hooks, the batch decision, persistence.
- "Off" reached by the same zero-scale path that an engine without a profile takes.

**Non-Goals:**
- Changing what "on" computes.
- Allocating or freeing direction tensors on switch: they stay uploaded, about 2.4 MB per session.
- Frontend changes (`640`).
- TP support for switching.

## Decisions

### D1. `steering_on` lives in `ds4_session`

The field sits beside `steering_in_think`. `ds4_session_create` sets it to "the engine has a profile", the same condition that decides whether the slot directions are uploaded today. A helper `ds41_engine_steered(e)` names that condition once.

### D2. Every scale passes through the flag

- `ds41_steering_apply_gates` starts from zero scales when `!s->steering_on`: no fold, no closure.
- `ds41_steering_on_prompt` / `ds41_steering_on_decode` return early when the flag is off, so phase tracking stops.
- A new `ds41_steering_arm(s)` is called by `ds4_session_create` and by the setter. It writes the constant scales of an ungated, unscheduled profile when on, and zeros when off.

The gated/scheduled path recomputes at the next `on_prompt` anyway. `arm` also covers the constant path, which never reaches `apply_gates`.

Alternative considered: free the direction tensors when off. Rejected because the routes already test the scale first, freeing would cost an allocation and a GPU write per switch, and "off" would then differ structurally from "on at zero".

### D3. `ds4_session_set_steering`

```
int ds4_session_set_steering(ds4_session *s, bool on);   /* 0 ok, 1 error */
bool ds4_session_steering(const ds4_session *s);
```

The setter works in this order:
1. Same value: return 0 and touch nothing.
2. `on` without a profile: return 1 with a message on stderr, the same style as `ds4_session_set_directional_steering_ffn`.
3. A distributed or TP session: return 1, because the worker ranks are not told.
4. Otherwise, if the session holds tokens (`checkpoint.len > 0`), call `ds4_session_invalidate(s)`. Then set the flag and arm the scales.

The invalidate drops the checkpoint and resets the graph, so the next `ds4_session_sync` sees no common prefix and evaluates the whole prompt.

### D4. Batch decision per item

The engine-wide gate/schedule test in `ds4_sessions_batch_supported` becomes a loop over the items:
- **Decline** when any two items differ in `steering_on`.
- **Decline** when an item has steering on and the profile is gated or scheduled.
- **Otherwise** continue to `ds41_sessions_batch_supported`.

A batch of steered sessions under a constant profile keeps today's batching, since every row then shares one scale. A batch of unsteered sessions is batched with any profile loaded. The test stays an `sf:` block next to the upstream lines it guards; there is no upstream conflict, because the block is ours already.

### D5. Persistence reads the flag

`ds41_steering_refuses_persistence` refuses when `s->steering_on`, instead of reading the graph's current scales. This closes a gap in today's check: a session whose gated slots are both at zero for the current token, for example a think-only slot during the answer, passed it and could save a payload that was computed steered. `650` adds the server's permission on top of this check.

### D6. Tests

**Model-backed**, a new mode in `tests/test_deepseek41_graph.c`, `--steering-session PROFILE PROMPT_FILE`, run by `make test-deepseek41-steering-session`. It opens engines one after another in one process at the 32 GiB cache that `AGENTS.md` allows for reopening, and compares the state digest it already uses for `--decode-switch` (logits, KV, Engram history), prefill plus 65 decoded tokens:
1. An engine without the profile; then an engine with it and the session off. The digests must be equal.
2. With the profile: session A, off, fresh. Session B, on, prefill, then switched off, then the same prompt synced again. B's digest must equal A's, and B's second sync must report that it evaluated the whole prompt.

**Model-less** (`make test`):
- the setter's error without a profile;
- the same-value no-op;
- the batch decision for mixed items, through a test hook that builds items with fake sessions, as the server tests build checkpoints with `ds4_session_new_test_checkpoint`.

"On" is covered by the CLI text comparison: the candor profile, thinking on and off, byte-identical to main.

## Risks / Trade-offs

- [A route reads the engine's scale instead of the session's] → Every route reads `g->residual_scale*` today; the model-backed case 1 would catch a stray engine read, since it compares against an engine with no profile at all.
- [Invalidation hides a bug in the server's routing] → It turns that bug into a re-prefill, never into a mixed state; `640` tests its routing on its own.
- [The persistence fix (D5) refuses a save that today succeeds] → Only for sessions that are actually steered; today's success there was the gap. No shipped flow saves steered sessions: the server skips the disk cache under a profile until `650`.
- [Mixed-steering batches decline even under a constant profile] → They must: one forward applies one scale.
