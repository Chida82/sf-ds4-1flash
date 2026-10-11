# Proposal

## Why

`--boost` asks fanboost for full fans by running `/usr/local/bin/fanboost max` (since `6553aa6`). When fanboost is not installed the spawn fails and nothing is said: the run goes on with Apple's fan curve, and the user believes the fans are boosted. The same happens when the binary is there but its daemon is not running: `fanboost max` writes its request, and nobody reads it. Since fanboost now ships in `fanboost/` with an installer, the engine can say exactly what is missing and how to fix it.

## What Changes

- **Refuse to start.** With `--boost`, engine open (CLI, server, bench) checks fanboost before loading the model. If the check fails, the engine prints one line saying what is missing and how to fix it, and exits with an error:
  - fanboost not installed: install it with `./fanboost/install.sh` (see `fanboost/README.md`), or run without `--boost`;
  - installed but its daemon not running: reinstall it with `./fanboost/install.sh`, or run without `--boost`;
  - any other failure of the check: its exit status, and the same two ways out.
- **Ask fanboost, do not inspect it.** The daemon check is a new `fanboost check` command, in the owner's fanboost repository: exit 0 when the daemon is running, 1 with a message otherwise. The engine runs it and reads only the exit status; it never reads fanboost's lease, notifications or `status` text. `fanboost/` is then copied again from that repository, as `AGENTS.md` prescribes.
- **Say it once if fanboost goes away later.** If `fanboost max` fails during a run (fanboost uninstalled while a server runs), the engine prints one warning and keeps running; the decode keep-alive part of `--boost` does not depend on fanboost.
- The `--boost` help line and the README's `--boost` paragraph say that the flag needs fanboost and that the engine refuses without it. Without `--boost` nothing changes.

Passing `--boost` without fanboost used to start the engine and now refuses it. The flag is recent (`220`, 2026-10-08) and has no users outside this machine, so the change is accepted as is; the decode keep-alive alone stays available through `DS4_METAL_V41_DECODE_KEEPALIVE=1`.

## Capabilities

### New Capabilities
- `boost-mode`: what `--boost` requires from the machine and how the engine reports a missing requirement.

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: `ds4_gpu_set_boost` returns success; the check and the runtime warning sit beside `ds4_gpu_fan_hint`.
- `ds4.c`: engine open stops when `ds4_gpu_set_boost` fails (the call added by `220`).
- `ds4_gpu.h`: the setter's return type.
- `ds4_help.c`, `README.md`, `AGENTS.md`: one sentence each.
- The owner's fanboost repository: `fanboost check`, then `fanboost/fanboost.c` and `fanboost/README.md` here.
- No effect on output, speed or any run without `--boost`; the A/B harness never passes `--boost`.
- Depends on nothing in `280`; either can land first.
