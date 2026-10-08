# Proposal

## Why

A streaming decode token keeps the GPU idle for long stretches: every layer waits about 120 us for the expert pass to start (`132`), and a layer with a miss waits about 1 ms for its reads (`145`). Apple GPUs drop to lower power states in such gaps, and the next kernels run at a lower clock. The Argodrive fork of ds4 (`argonautlabsai/ds4-argodrive`) measured two keep-alives on V4.1 decode with expert streaming: a tiny ALU kernel on a second queue for the whole decode token (`DS4_ARGODRIVE_GAP_KEEPALIVE=2`, about +3.4% decode), and one busy CPU thread at user-interactive QoS during decode (`DS4_ARGODRIVE_CPU_KEEPALIVE`, about +3% together with a read split this child does not have), at the cost of a few watts. This child already has the GPU half: the TP keep-alive thread and `kernel_dsv4_tp_keepalive`, started only by `ds4_gpu_tp_init`. On a single streaming box nothing keeps either the GPU or the CPU awake.

## What Changes

- S1: on a single streaming box, the existing keep-alive thread (its own queue, one threadgroup, `DS4_TP_KEEPALIVE_ITERS`/`_TGS` as in TP) runs while a decode token is being evaluated and pauses outside it, so prefill and idle time pay nothing. Switch `DS4_METAL_DISABLE_V41_DECODE_KEEPALIVE`.
- S2: one CPU thread at `QOS_CLASS_USER_INTERACTIVE` spins with `yield` during the same span, so the cluster that runs the per-layer bookkeeping holds its clock. Switch `DS4_METAL_DISABLE_V41_CPU_KEEPALIVE`. Measured as its own step.
- Output is unchanged by construction (the keep-alive kernel writes only its own buffer): checked bitwise with `make test-deepseek41-decode-switch` for each switch.
- Expected: low single digits on decode, if the gate shows the clock sagging; a few watts more during decode.

## Capabilities

### New Capabilities
None. Same results, different power state (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: start/pause of the keep-alive thread outside TP; the CPU spinner (S2). `ds4.c` or the session eval path: token-scope begin/end calls on the V4.1 single-box streaming decode. `ds4_gpu.h`: declarations.
- `AGENTS.md` switch list; `docs/upstream-prs.md` "Ideas from other forks" lines for the two Argodrive commits.
- TP keeps its own keep-alive unchanged; resident decode and prefill are not touched. No external SSD.
