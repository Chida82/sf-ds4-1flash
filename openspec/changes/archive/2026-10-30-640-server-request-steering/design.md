# Design

## Context

After `630`, a session has `ds4_session_set_steering`. Switching it drops the session's live state, and the batch decision is made per item. After `620`, the server's only steering input is `--steering-profile`, and with it the server skips `--kv-disk-dir` (`ds4_server.c:14961`).

Server structure that this change touches:

- **Request parsers.** `parse_chat_request`, `parse_anthropic_request`, `parse_responses_request` and `parse_completion_request` read `model` into `request.model` (`model_from_request` set). Each applies the alias thinking rule at `3725`, `3941`, `4970`, `5176`.
- **Aliases.** `server_model_alias_known` (`1247`), `model_alias_disables_thinking` and `model_alias_enables_thinking` (`1228-1235`) compare whole ids.
- **Model list.** `/v1/models` (`send_models`, `14203`) lists only `deepseek-v4.1-flash`. `/v1/models/<id>` (`14341`) answers for any known alias.
- **Per-request session setup.** `generate_job` (`13810`) sets the cancel hook and the think level, then runs `generate_job_inner`.
- **Slot choice.** `slot_probe_reuse_locked` (`10834`) scores how much of a slot's live state a request can reuse. It already has one gate of the same kind: images whose fingerprints do not extend the slot's.
- **Logs.** Progress lines carry `log_flags` (`think`, `tools`, ...). The request trace prints `think_mode` (`11229`).
- **Startup.** `cfg.engine.tp.role` and `cfg.engine.distributed.role` (`14871`, `14881`) identify TP and distributed roles.

## Goals / Non-Goals

**Goals:**
- One request field, `steering`, decided once at parse time and read everywhere else.
- Every path that consumes a slot's live state sees it.
- Startup errors for the configurations the spec forbids.

**Non-Goals:**
- The disk KV cache (`650`); in this change it stays skipped while a profile is loaded.
- Several profiles.
- TP support.
- A JSON steering field.

## Decisions

### D1. Configuration

- **New option.** `--steering-profile-on-request NAME|FILE` sets `cfg.engine.steering_profile`, so the engine loads and validates it exactly as for the CLI, and also sets `cfg.steering_on_request = true`.
- **Old option.** The `--steering-profile` branch stays in the parser and exits 2 with the message of the spec. Without the branch an old command line would read "unknown option", which does not point anywhere.
- **TP and distributed.** After parsing, if `steering_on_request` is set and `cfg.engine.tp.role != DS4_TP_NONE || cfg.engine.distributed.role != DS4_DISTRIBUTED_NONE`, the server exits 2 naming the combination. This check sits with the existing configuration checks (`14790`) and runs before the model loads.
- **Slots start off.** After the slots' sessions are created, the server calls `ds4_session_set_steering(session, false)` on each. They are empty, so nothing is invalidated. The initial state then matches "no request has steered yet".

### D2. Model ids

There is one helper, `model_id_split(const char *id, size_t *base_len)`, which returns whether the id ends in `-steering` and the length of the base id. The three alias predicates compare the base (`strncmp` with `base_len` plus a length check), so `deepseek-chat-steering` still disables thinking unless an explicit control was sent.

Each parser stores `r->steering = model_id_split(r->model, ...)` where it already reads `model`. `r->model` keeps the requested id, which the response echoes unchanged.

One check, `request_steering_check(s, r, err)`, is called where a parsed request is accepted for queueing (the same place an invalid request becomes a 400). It returns 400 when the request is steering and no profile is loaded, or when its base id is unknown. Keeping it out of the four parsers keeps the parsers free of server state.

### D3. Model list

`send_models` appends a second entry, `deepseek-v4.1-flash-steering`, when `s->steering_on_request`. To make it testable without a socket, its body moves into `append_models_list(buf *, const server *)`. `/v1/models/<id>` resolves `-steering` ids through the same split, and only when a profile is loaded.

### D4. Per-request switch

`generate_job` calls `ds4_session_set_steering(slot->session, j->req.steering)` next to `ds4_session_set_think_level`, before any sync. A nonzero return fails the request with a server error. It cannot happen outside TP, which D1 refuses at startup. The engine's drop of live state on a change (`630`) is the backstop for every path below.

### D5. Live-state isolation: the inventory comes first

The first task lists every server path that consumes or produces a slot's live state, and decides each one. The known paths and the rule for each:

| Path | Where | Rule |
|---|---|---|
| Slot probe and routing scores | `slot_probe_reuse_locked` | new gate: `ds4_session_steering(slot->session) != req->steering` → `REUSE_NONE`, next to the vision gate |
| Live prefix sync / rewind | `11624-11779`, `12589` | runs after D4's switch, so a mismatched slot is already empty; no change |
| Live tool state / exact DSML replay | `live_state_contains_all`, `tool_memory_attach_to_messages` | live tool state belongs to the slot; cleared with the slot when the steering differs (checked in the inventory) |
| Resident checkpoints and eviction tiers | routing scores | covered by the probe gate |
| Decode batch membership | engine (`630`) | no server change |
| Disk cache paths | `kv_cache_*` | skipped while a profile is loaded (unchanged); `650` |

When a path does not fit this table, the inventory records it and the design is updated before code changes.

### D6. Logs

- `log_flags` gains `steer` when `j->req.steering`.
- The trace gains `steering: on|off` after `think_mode`.

### D7. Tests

**Model-less** (`./ds4_test --server`, run by `make test`):
- `model_id_split` and the alias predicates on all six ids;
- `request_steering_check`: with and without a profile, unknown base id;
- `append_models_list` with and without a profile;
- the probe gate: two test checkpoints, one marked steered, and a request of each kind;
- the startup checks (old flag, TP or distributed with the new flag), through the configuration-check function rather than a process exit.

**Model-backed acceptance**, greedy, thinking on and off, one long and one short prompt, run by hand and recorded in the tasks:
1. On the branch, a server with the profile and requests without the suffix, against main (with `630`), a server without any profile: identical tokens and usage.
2. On the branch, `deepseek-v4.1-flash-steering`, against main, a server with `--steering-profile` and `deepseek-v4.1-flash`: identical tokens and usage.
3. On the branch with one slot, the spec's alternating sequence: each request reports full prompt evaluation in the log, and the third response equals the first.

## Risks / Trade-offs

- [A reuse path not in the inventory extends a mismatched slot] → The engine drops live state on every switch (`630`), so the result is a re-prefill, never a mixed state.
- [Clients that loop over `/v1/models` see a second id] → Only on a server started with a profile, which is the point.
- [With one slot, alternating clients re-prefill every time] → Inherent to isolation. Documented next to `--batched-sessions` in `docs/SERVER.md`, together with the `650` disk cache that recovers it.
- [The old flag's message branch is dead weight] → One branch, kept for the first months after the rename. It can go in a later cleanup.
