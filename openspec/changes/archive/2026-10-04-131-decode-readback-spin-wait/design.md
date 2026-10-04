# Design

## Context

`130` S0: per layer, router command buffer A is committed and waited (`ds4_gpu_end_commands` -> `ds4_gpu_finish_command_buffer` -> `waitUntilCompleted`), the CPU reads six ids, prepares bindings, encodes the expert command buffer B and flushes it. Probe on `main` at `bfa0ef2`: 76 us from A's `GPUEndTime` to the CPU's return from the wait, 115 us of CPU work, 103 us from B's commit to its `GPUStartTime`. A takes about 430 us of GPU time, so a poll that starts when A is committed would spin about that long per layer.

## Goals / Non-Goals

**Goals:** cut the wake-up part of the readback gap, bitwise output.

**Non-Goals:** removing the readback (that is `132`), changing encoding or the flush schedule, MTL4 submission, a polling thread, unbounded spinning.

## Decisions

### D1. Gate

On the post-`130` tree, re-measure the wake component with the `130` probe method. A wake under 20 us per layer closes the change.

### D2. Bounded poll

Poll `cb.status >= MTLCommandBufferStatusCompleted` (or the shared event's `signaledValue`) with a pause instruction between reads, for at most a fixed bound (start from about 1 ms, A's GPU time plus margin), then call the existing blocking wait. Pick the primitive that wakes faster in a micro-probe on the real decode; keep one. Error and timeout handling are those of the blocking path, which still runs to collect status. The poll applies only to the streaming decode readback, not to prefill or TP frames.

### D3. Evidence

Bitwise logits/state with `make test-deepseek41-decode-switch` and the rollback switch; normal harness `decode,append` with long and cold guards, `--bitwise`. Report the wake component before and after. Keep under the per-step rule; an additive neutral poll is removed.

## Risks / Trade-offs

- Spinning costs power and steals a core from the expert pread pool -> the bound, and the harness measures the net.
- A late GPU makes every wait hit the bound -> the blocking fallback keeps correctness; the probe reports how often the bound is reached.

## Migration Plan

Branch `perf/131-decode-readback-spin-wait`. One rollback switch for the bitwise test; no user option. No commit or push without a request.
