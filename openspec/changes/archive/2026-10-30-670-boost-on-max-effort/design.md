# Design

## Context

How `--boost` is built today:
- `ds4_gpu_set_boost(bool)` (`ds4_metal.m`) runs at engine open. It runs `fanboost check`, prints one of three refusals naming `--boost`, and on success sets the file-static `g_boost` to 1 and fires one fan hint before the model loads.
- `g_boost` is read in two places, both at runtime:
  - `ds4_gpu_fan_hint`, on every command batch, spawns `fanboost max` at most once a second;
  - `ds4_gpu_decode_keepalive`, once per decode token, arms the keep-alive burst. It creates the keep-alive thread lazily at the first armed token and leaves it paused when not armed.

  So flipping `g_boost` between tokens is already well defined. No other code reads it.
- The server runs every request through `generate_job(s, slot, j)` (`ds4_server.c`), from `worker_main`, or from `slot_worker_main` under `--batched-session`. There `j->req.think_mode` already holds the thinking mode after `610`'s precedence: an explicit disable has turned `max` into `DS4_THINK_NONE`. `ds4_think_mode_effort_level(mode)` is 100 for `DS4_THINK_MAX` and for the numeric level `"100"` (`ds4_think_mode_level` covers only the numeric modes and returns -1 for `DS4_THINK_MAX`).
- The server refuses invalid flag combinations before loading in `server_config_check_steering`, which unit tests already cover.

## Goals / Non-Goals

**Goals:**
- One counter in the server decides boost. The GPU layer gets only a setter, so the decision stays where the requests are.
- A server without the flag runs no new code path and no fanboost command.

**Non-Goals:**
- No per-token or per-phase boost, for example only during thinking. The unit is the request.
- No cool-down handling. When boost turns off, `fanboost max` stops being sent and the daemon returns the fans to Apple's curve on its own lease timeout, as at the end of a `--boost` run.

## Decisions

### 1. Split the check from the state in `ds4_metal.m`

- `int ds4_gpu_boost_check(const char *flag)` holds today's check and its three messages, with `flag` substituted for the literal `--boost`.
- `void ds4_gpu_boost_active(bool on)` stores `g_boost`.
- `ds4_gpu_set_boost(bool)` stays, as check + active + fan hint, so `--boost` is byte-for-byte the same behaviour.

`g_boost` becomes an `int` accessed with `__atomic_store_n` / `__atomic_load_n` (relaxed). It is now written by a server thread and read by the decode thread and the fan-hint path. On arm64 a relaxed load is the same `ldr` as today's plain read.

*Alternative:* call `ds4_gpu_set_boost(true)` per request. Rejected: it would spawn `fanboost check` on every max request and print `--boost` in its errors.

### 2. Engine option plus one engine call

- `ds4_engine_options` gets `bool boost_on_request`.
- At open, the Metal branch calls `ds4_gpu_boost_check("--boost-on-max-effort")` and leaves `g_boost` at 0. Without the option it calls nothing, which preserves the "nothing changes" requirement.
- `void ds4_engine_set_boost(ds4_engine *e, bool on)` forwards to `ds4_gpu_boost_active` only when the engine was opened with `boost_on_request`. Otherwise it is a no-op.
- The CPU build (`DS4_NO_GPU`) compiles it as a no-op.

*Alternative:* let the server call the GPU layer directly. Rejected: the server links only against `ds4.h`, and every other runtime switch goes through the engine.

### 3. A counter of active max jobs in `generate_job`

- `server` gets `int boost_jobs`, guarded by `model_mu`, which `generate_job` already takes at its start and end.
- A job whose `ds4_think_mode_effort_level(j->req.think_mode) == 100` increments it before `generate_job_inner` and decrements it after.
- The 0→1 and 1→0 transitions call `ds4_engine_set_boost` and log one line each. The on line names the request id.
- The rule "on while any max job is active" therefore needs no batch awareness. A max job on a slot keeps the counter above zero for as long as the decode batch serves it.
- The predicate and the transition logic are two small static functions, so the unit tests reach them without an engine.

*Alternative:* decide per decode batch, in the decode worker. Rejected: it adds a hook in the hot loop for the same result at request granularity.

### 4. Flag handling

- `--boost-on-max-effort` sets `c.engine.boost_on_request`.
- `server_config_check_steering` is generalised into the server's pre-load check (renamed `server_config_check`). It also refuses `boost && boost_on_request`, with an error naming both flags.
- The CLI, bench and eval do not parse the new flag.

## Risks / Trade-offs

- [A job that fails before generating still holds the counter until `generate_job` returns] → harmless: boost lasts as long as the job does, and the decrement sits on the single exit path.
- [A long max thinking run keeps the fans at 100% for minutes] → this is the requested trade. The log lines make it visible.
- [Fanboost dies mid-run] → unchanged: `ds4_gpu_fan_hint` warns once and generation continues (existing requirement).
- [The 0→1 switch lands in the middle of the first token] → that token may run without the keep-alive. Output is unaffected, and from the next token boost is fully on.

## Migration Plan

None: a new opt-in flag. Rollback means starting the server without it.

## Open Questions

None.
