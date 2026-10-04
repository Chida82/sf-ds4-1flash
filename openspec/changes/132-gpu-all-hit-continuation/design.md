# Design

## Context

Per layer today: command buffer A (attention, router) is committed and waited; the CPU reads `selected` (six ids), peeks the expert cache (recency and hit counters), loads misses through the pread pool, fills the layer's address-table slots, encodes command buffer B (routed experts through `kernel_mul_mv_addr_iq2_xxs_pair_swiglu_masked_f32` / `kernel_mul_mv_addr_q2_K_sum6_masked_f32`, then the rest of the layer) and flushes it at layer end. `130` S0 on `bfa0ef2`: A to B gap about 295 us = 76 wake + 115 CPU + 103 commit-to-start; GPU busy 28.5-30.6 ms of a 40.9-41.8 ms token. All-hit layers: 90% in decode 2048/8192 after the sweeps, 97.7% in a 2500-token answer. The address-table and masked kernels, the `selected_exec` buffer path and an opt-in GPU hit validator already exist; `ds4_gpu_signal_batch_and_wait_event` already uses a shared event for the Q4 readback.

## Goals / Non-Goals

**Goals:** remove the expert pass's encode and submission latency from the per-layer critical path, bitwise output, unchanged cache policy.

**Non-Goals:** speculative execution with rollback, GPU-side miss servicing, changing which experts are cached, MTL4 migration, changes to prefill or TP frames.

## Decisions

### D1. Gate

After `130` (and `131` if run), re-measure per-layer wake, CPU and commit-to-start components. Close if the encode-plus-queue part is under 50 us per layer.

### D2. Event-gated, pre-committed expert pass

For each layer: commit A, then commit B immediately, its first command a wait on shared event value `v`. B takes ids from the router's output buffer, not from a host copy, and addresses from the layer's address table. The CPU waits for A (existing path, or `131`'s), reads the ids, runs the existing cache peek and miss loading, writes the address-table slots for this token's experts, and signals `v` from the CPU. The GPU starts B on the signal.

Ordering rules: a slot B reads is written before the signal and not recycled until B completes (the existing in-flight marking covers it: the entries are protected for the current selection). The address table is per layer, so the next layer's writes cannot race B. An error or cancellation before the signal still signals (so B runs on valid or zeroed inputs and the queue drains), then the token fails as today; no command buffer is left waiting forever.

### D3. Bookkeeping stays put

Hit, miss, recency and hotness updates happen on the CPU between A and the signal, exactly where they happen now, so `--cache-stats` counters and evictions are equal to the previous tree. Where the existing selected-id host buffer feeds a kernel, it is replaced by the GPU buffer only for B; the host still reads the ids.

### D4. Rejected: optimistic continuation

The GPU running ahead with a miss flag and the token restarted from the first missing layer needs snapshots of every in-place state (KV, compressor, indexer) and costs a restart whenever any of 40 layers misses: 98.5% of tokens in short answers, 61% in long ones. Not designed further.

### D5. Evidence

Fixtures: forced misses on chosen layers, a delayed signal, a load error before the signal, cancellation mid-token, checked against the previous path bitwise. Model-backed: `make test-deepseek41-decode-switch` with the rollback switch, graph queue parity, cache counters equal. Harness: `decode,append` with long and cold guards, `--bitwise`; the gain must clear the per-step rule (over 800 runtime lines it needs +1.5%).

## Risks / Trade-offs

- A command buffer waiting on an event that is never signalled hangs the queue -> every exit path signals; a fixture covers it.
- Reading ids on the GPU changes which buffer a kernel binds -> bitwise switch test and exact-output fixtures.
- Shared-event signal latency may eat the gain -> D1/D5 measure the gap components on the real decode.

## Migration Plan

Branch `perf/132-gpu-all-hit-continuation`. One rollback switch for the bitwise test, removed if the step is not kept. No commit or push without a request.
