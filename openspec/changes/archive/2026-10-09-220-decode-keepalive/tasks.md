# Tasks

Data first. The launch flag's shape was decided from the measurements: `--boost`, opt-in (D3).

## 1. Prototype (environment variables only)

- [x] 1.1 On `perf/220-decode-keepalive`, start the TP keep-alive thread on a single streaming box, scoped to the decode token, with a duty cycle (S1), behind `DS4_METAL_V41_DECODE_KEEPALIVE=1` and `_DUTY=<percent>`. Default off. Verify `make test` and `make test-deepseek41-decode-switch` bitwise between off and on.
- [x] 1.2 Write the gate script in the scratchpad: it waits for pressure 0 and the GPU below 50 C, runs alternating off/on decode pairs, and logs mactop (pressure, GPU MHz, GPU and CPU W, temperatures, fan rpm) once a second. Dry-run one pair.

## 2. S1 gate: keep-alive for the whole decode token

- [x] 2.1 Nominal short runs, 6 pairs at duty 100: tok/s, GPU MHz, GPU and CPU W, max temperature, pressure at the end.
- [x] 2.2 Heavy sustained: harness `decode` A/B with B on, 30 minutes, `--bitwise`.
- [x] 2.3 Record S1 in `perf-record.md` (tables and a Rejected ideas row; no regime gained, so no duty sweep), with both CPU clusters' clocks.

## 3. S1b: keep-alive during the miss reads

- [x] 3.1 Turn the prototype into S1b (D2):
  - the decode token scope stays;
  - the thread is unpaused only inside `ds4_gpu_stream_expert_pread_pool_wait`;
  - bursts of `DS4_METAL_V41_DECODE_KEEPALIVE_BURST_US`, default 200;
  - the duty cycle is deleted;
  - waits per token and their time are logged in the `--cache-stats` report, next to the mailbox line (128 tokens at 2048: 3.8 waits and 2.5 ms per token).

  Verify `make test`, `make cpu`, and the decode-switch test bitwise at 1 and 8 threadgroups.
- [x] 3.2 Add cluster clocks (Super and Performance MHz and active) to the gate script. Run the D1 gate at 1 and 8 threadgroups: Nominal 6 pairs each, then the Heavy harness A/B at the better width.
- [x] 3.3 In a regime that gained, sweep bursts of 100 and 500 us. Record the tables in `perf-record.md`. If no regime gained, add a Rejected ideas row and remove the S1b code.

## 4. S2: CPU spinner

- [x] 4.1 A user-interactive spinner thread with `yield`, active only during a decode token, blocked between tokens, behind `DS4_METAL_V41_DECODE_CPU_KEEPALIVE=1` (D4). Verify `make test`, `make cpu`, and the decode-switch test bitwise.
- [x] 4.2 D1 gate (Nominal 6 pairs, Heavy harness 30 minutes), with both clusters' clocks. Record in `perf-record.md`. If no regime gained, add a Rejected ideas row and remove the spinner.

## 5. Time in each pressure state (request-shaped workload)

- [x] 5.1 Script a session of typical requests:
  - prompts of 1k-10k tokens and answers of 200-2000 tokens, with idle gaps between them, about 30 minutes;
  - for each request, its tok/s and the seconds spent at Nominal, Moderate and Heavy.

  Run it with no keep-alive, then with what 3 and 4 kept, if anything.
- [x] 5.2 Request-scoped fans, in the separate `fanboost` repo:
  - when a request starts the fans go to 100%; 8 s after it ends they go back to the Apple curve, so the next request starts from a cooler machine;
  - it needs a non-root hint from the engine to the root daemon, for example a `notify_post` the daemon listens to.

  The daemon is not running today, and changing or installing it is a system change: ask before doing it, and before any `sudo`. Do not start this task without the owner's go.

  Done by the owner: `fanboost set`/`unset` and the lease file `/tmp/fanboost.lease`, no root needed. The sessions renewed it from the client; `--boost` renews it from `ds4_gpu_begin_commands`.
- [x] 5.3 Repeat 5.1 with fans only, and with what was kept plus fans. Table: tok/s per request and time per state across the configurations, i.e. how many seconds in the better states each one buys.

## 6. Decide and integrate

- [x] 6.1 `--boost` (D3):
  - wire the engine option into the CLI, server and bench;
  - the paused thread waits on a condition variable;
  - if 5.3 pays, `--boost` also sends the fan hint while a request runs.

  Verify `make`, `make cpu`, `make test` and the decode-switch test.
- [x] 6.2 Harness A/B of this tree with `--boost` (B) against the previous kept tree, `decode,append` with the guards, `--bitwise`; keep rule; record the row with watts.
- [x] 6.3 Finish the change:
  - review against `AGENT.md`;
  - update `AGENTS.md` (flag, switches) and the README's everyday-use section;
  - update the `docs/upstream-prs.md` line for Argodrive's keep-alives;
  - run the model-backed checks and the parity oracle;
  - run `openspec validate 220-decode-keepalive --strict`.

  The segment-start A/B joins the end-of-batch measurement. No commit or push without a request.

  Done 2026-10-09: parity OK (10 prompts, token-identical); `ds4_test` with streaming OK on every group but `--tool-call-quality`, stopped after an hour in its `--quality` streaming branch (unfused kernels map whole layers: GPU 3%, 5.9 GB/s of reads); that branch runs no code this change touches.
