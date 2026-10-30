# Proposal

## Why

`--boost` (`220`, `290`) made request-shaped sessions about 4.7% faster by holding the fans at 100% and keeping the GPU busy while a decode token reads missing experts. On a server it is all or nothing: either every request pays the fan noise, or none gets the gain. The owner wants the server to boost only the requests that ask for the most thinking, `reasoning_effort` `max`. Those are the long ones, where the gain matters and the machine heats up anyway. A service started by `sfctl` (next change) will carry this flag in its per-model config.

## What Changes

- **New server option `--boost-on-max-effort`.**
  - At engine open it checks fanboost exactly like `--boost` (`fanboost check`). If fanboost is missing or its daemon is down, the server refuses to start. The message names `--boost-on-max-effort`, not `--boost`.
  - After the check, boost stays **off**. It does not run `fanboost max` during model load, as `--boost` does.
- **Boost follows the requests.**
  - Boost is on while at least one request with effort level 100 is generating. The trigger is the request's thinking mode after `610`'s precedence: `max` on any API, or the numeric level `"100"`.
  - Boost turns off when the last such request ends.
  - `xhigh` (90) and lower levels do not trigger it, and neither does a request whose thinking is disabled.
  - With `--batched-session`, one max request boosts the whole machine while it runs, because fans and GPU clock are shared. The other requests in the batch get the speed too.
- **Same two effects as `--boost`.**
  - The fan hint: `fanboost max` at most once a second while the GPU has work.
  - The single-box decode keep-alive.

  Both already read the boost state at runtime, per command batch and per token, so turning boost on or off between requests needs no restart. `DS4_METAL_V41_DECODE_KEEPALIVE=0|1` still overrides the keep-alive per token.
- **`--boost` and `--boost-on-max-effort` together are rejected** at startup with an error. `--boost` already means "always on".
- **Server only.** The CLI, bench and eval keep `--boost` as it is. They have no requests to select.
- **Output does not change.** Boost changes fan speed and GPU idle work, never the computation: greedy tokens stay bitwise identical with and without the option.
- **One log line per transition:** boost on, with the request that started it, and boost off. This makes the behaviour visible in the service log.

Non-goals:
- No per-request JSON field and no model alias for boost.
- No threshold other than level 100.
- No change to `--boost` itself, to fanboost, or to the keep-alive kernel.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `boost-mode`:
  - adds the server's per-request boost: the trigger level, the batched rule and the startup refusal under the new flag name;
  - widens "Without boost nothing changes" to cover the new flag.

## Impact

- **Code:**
  - `ds4_metal.m`: split the fanboost check out of `ds4_gpu_set_boost`, and add a setter that changes the boost state without re-checking.
  - `ds4_gpu.h`.
  - `ds4.h` / `ds4.c`: one engine option and one engine call. The CPU build gets a no-op.
  - `ds4_server.c`:
    - parsing and the conflict check;
    - a counter of active max-effort jobs in `generate_job`;
    - unit tests.
  - `ds4_help.c`.
- **Docs:**
  - `README.md`: the `--boost` section;
  - `AGENTS.md`: the `--boost` paragraph;
  - `fanboost/README.md`, if it lists the engine flags.
- **Clients:** none breaks. A server started without the flag behaves exactly as today.
- **Speed:** no new speed claim. Max-effort requests get `--boost`'s measured gain, and the other requests run as without boost. The default path (no flag) is unchanged, so the A/B harness, which never passes `--boost`, is unaffected.
- **Upstream:** no upstream commit is involved. `docs/upstream-prs.md` is not touched.
- **Order:** after `610` (effort levels) and before the `sfctl` change, whose ds4-1flash config uses this flag.
