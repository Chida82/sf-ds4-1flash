# Design

## Context

- `--boost` is parsed by the CLI (`ds4_cli.c`), server (`ds4_server.c`) and bench (`ds4_bench.c`) into `ds4_engine_options.boost`; eval has no such flag. `ds4_engine_open_internal` (`ds4.c`) calls `ds4_gpu_set_boost(opt->boost)` right after `ds4_gpu_init`, before the streaming cache is configured and before any weight is read, and every other failure there already prints one `ds4:` line and returns 1.
- `ds4_gpu_set_boost` (`ds4_metal.m`) only stores the flag. `ds4_gpu_fan_hint` then spawns `/usr/local/bin/fanboost max` from a background queue at most once a second and ignores the result.
- fanboost today has `status` (always exit 0, Italian text), `max`, `release`, `pause`, `resume`, `help`, `run`, `-t`. Nothing answers "is the daemon up?" with an exit status. The daemon publishes an `ST_UP` bit in the state of the notification `com.chida82.fanboost.state` for `status`; that bit is fanboost's internal protocol.
- `fanboost/` here is a verbatim copy of the owner's repository (`AGENTS.md`), so fanboost changes are made there and copied.

## Goals / Non-Goals

**Goals:**
- One line on stderr that names the cause and the fix, then a non-zero exit, before any model loading.
- The engine depends on fanboost's command names and exit statuses only.

**Non-Goals:**
- Installing or starting fanboost from the engine.
- Checking whether the fans actually reached their maximum.
- Changing the decode keep-alive or its `DS4_METAL_V41_DECODE_KEEPALIVE` override.

## Decisions

### D1. `fanboost check` in fanboost
A new command: exit 0 when the daemon is running, otherwise exit 1 with one line on stderr. It reads the same state `status` reads (`ST_UP`); the meaning stays inside fanboost. Its help line and README row are added there, and the self-test is unchanged (no logic in `update`, `lease_active`, `req_step` or `fans_step` moves).

- *Alternative: parse `fanboost status`.* Ties the engine to Italian text that the owner changes often. Rejected.
- *Alternative: read `com.chida82.fanboost.state` from the engine.* The same coupling to fanboost's protocol that `6553aa6` removed. Rejected.
- *Alternative: check the binary only.* Misses the daemon-down case, which looks the same to the user as a boost that works. Kept only as the first half of the check.

### D2. The check at engine open
`ds4_gpu_set_boost(bool)` becomes `int ds4_gpu_set_boost(bool)`: when enabled, it runs `/usr/local/bin/fanboost check` synchronously (`posix_spawn`, `waitpid`, stdout and stderr to `/dev/null`) and maps the outcome:

| Outcome | Message (one line, `ds4:` prefix) |
|---|---|
| spawn fails with `ENOENT` | `--boost needs fanboost, which is not installed (/usr/local/bin/fanboost): install it with ./fanboost/install.sh (see fanboost/README.md), or run without --boost` |
| exit 1 | `--boost needs the fanboost daemon, which is not running: reinstall it with ./fanboost/install.sh, or run without --boost` |
| any other failure | `--boost: fanboost check failed (<cause>): see fanboost/README.md, or run without --boost` |

It returns 0 on any failure; `ds4_engine_open_internal` closes the engine and returns 1, as for the other startup failures. On success it sends one `fanboost max` at once, so the fans are already up when the model starts loading.

- *Alternative: warn and continue.* The user asked for an error, and a warning scrolls away in a server log. Rejected.
- *Alternative: check in each frontend.* Three copies of the same code, and the bench or a future frontend can forget it. Rejected.

### D3. One warning on a later failure
`ds4_gpu_fan_hint` keeps its background spawn; when `posix_spawn` fails or `fanboost max` exits non-zero, a static flag lets it print `ds4: --boost: fanboost max failed (<cause>); the fans are on Apple's curve` once per process. The keep-alive is not touched.

### D4. The path stays a constant
`/usr/local/bin/fanboost` is where `fanboost/install.sh` puts it and the only path the daemon's plist names. A test of the missing case builds a scratch copy with the path changed by `sed`, as fanboost's own development notes do for thresholds; no `SF_*` define or environment variable is added for it.

## Risks / Trade-offs

- [`fanboost check` lands in the owner's repository later than this change] → task 1 comes first; until the copy has `check`, every `--boost` start would report a daemon failure, so the engine part does not land without it.
- [The check adds a process spawn to startup] → a few milliseconds against tens of seconds of model loading, and only with `--boost`.
- [Someone used `--boost` for the keep-alive alone] → the flag is two days old with no users elsewhere; `DS4_METAL_V41_DECODE_KEEPALIVE=1` gives the keep-alive without fanboost, and `AGENTS.md` already documents it.

## Migration Plan

Users of `--boost` install fanboost (`./fanboost/install.sh`) or drop the flag. Rollback is reverting the engine commit; `fanboost check` can stay.
