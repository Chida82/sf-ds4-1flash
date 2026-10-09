# Proposal

## Why

A streaming decode token keeps the GPU idle for short stretches: every layer waits about 100 us for the expert pass to start (`132`, `210`), and a layer with a miss waits about 1 ms for its reads (`145`). Apple GPUs drop to lower power states in such gaps. The Argodrive fork of ds4 (`argonautlabsai/ds4-argodrive`) measured two keep-alives on V4.1 decode with expert streaming:
- a tiny ALU kernel on a second queue, run **only while the CPU waits on the pread pool** (its mode 1, `DS4_TP_KEEPALIVE_TGS=8`, `ITERS=300000`), about +3.4% decode (17.34 to 17.93 t/s). Its continuous mode gained nothing;
- one busy CPU thread at user-interactive QoS (`DS4_ARGODRIVE_CPU_KEEPALIVE`), about +2.6-3.0%, which came from the cluster clock (3.4 to 4.2 GHz). Their baseline also had a busy bookkeeping thread.

This child already has the GPU half, the TP keep-alive thread and `kernel_dsv4_tp_keepalive`, but only `ds4_gpu_tp_init` starts it.

The `210` A/B logs, mactop once a second, show the machine leaving thermal pressure Nominal within the first minutes of sustained work and then staying at Heavy (2106 of 2190 samples, and 2494 of 2585 in the afternoon run). Interactive use, one request after an idle pause, starts at Nominal; every harness A/B so far was measured almost entirely at Heavy. So each keep-alive is gated in both regimes.

The first step, S1, ran the keep-alive for the whole decode token and lost in both regimes (`speed-bench/perf-record.md`, Decode keep-alive after 210):
- **Nominal:** -1.6% (6 cool-start pairs, CI below zero). Inside the decode window the GPU is already at 1620 MHz and 100% active, so it has no gap to fill.
- **Heavy:** decode 2048 -2.0%, decode 8192 -1.8% (CIs below zero), at the same clock and watts.

This matches Argodrive's continuous mode. What remains to test is their winning shape, the keep-alive only during the reads of missing experts, where the GPU has nothing queued for about 1 ms.

The same gate measured the CPU clusters during decode:
- **Super cluster (6 cores, where the decode thread spins since `131` and `210`):** 4.6 GHz, its top step, 95% active.
- **Performance cluster (12 cores):** 2.2-2.3 GHz, 46% active.

Argodrive's CPU gain came from a cluster that was not at its top. Here the decode thread's cluster already is, so a spinner can only help if the work that waits on the CPU (the commit to the GPU start, about 100 us per layer) runs on the Performance cluster.

## What Changes

- S1, the keep-alive for the whole decode token with a duty cycle: measured and dropped. It is recorded under Rejected ideas.
- S1b: the same thread and kernel, unpaused only while a decode token waits for missing expert reads (`ds4_gpu_stream_expert_pread_pool_wait`), in short bursts so it stops soon after the reads end. Threadgroups and burst length are swept. Behind `DS4_METAL_V41_DECODE_KEEPALIVE=1`, default off.
- S2: a CPU spinner at user-interactive QoS, active only during a decode token, behind `DS4_METAL_V41_DECODE_CPU_KEEPALIVE=1`, default off. It is measured on its own, whatever S1b's verdict.
- The launch flag is `--boost` in the CLI, server and bench, off by default (owner's decision after the gates). S1b pays only on a cool machine and never loses when it runs hot, so there is no `auto`. If the fan sessions pay, `--boost` also drives the request-scoped fans.
- Time in each pressure state on a request-shaped workload, then with request-scoped fans from the owner's `fanboost` daemon: 100% at request start, back to the Apple curve 8 s after the end. The runs use whatever S1b and S2 keep, or no keep-alive at all if neither is kept. The fan part lives in the `fanboost` repo, changes a system daemon, and waits for the owner's go.
- If neither keep-alive is kept and the fans do not pay, the change closes with no runtime code.
- Output is unchanged by construction: the GPU kernel writes only its own buffer, and the spinner touches no engine state. Each switch is checked bitwise with `make test-deepseek41-decode-switch`.

## Capabilities

### New Capabilities
None. Same results, different power state (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`:
  - the keep-alive thread start shared with TP;
  - the token scope and the unpause around the pread pool wait;
  - the CPU spinner;
  - the thermal-pressure read, if `auto` is needed.
- `ds4.c` and the frontends: one engine option and the `--boost` flag. `ds4_gpu.h`: declarations.
- `AGENTS.md` (switch list, flag) and `docs/upstream-prs.md` ("Ideas from other forks").
- TP keeps its own keep-alive unchanged. Resident decode and prefill are not touched. No external SSD.
