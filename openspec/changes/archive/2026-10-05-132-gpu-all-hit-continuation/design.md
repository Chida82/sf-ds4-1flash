# Design

## Context

Per layer today, the batch holding attention, router and shared expert is committed and waited at the selected-id readback; the CPU reads `selected` (six ids), peeks the expert cache, loads misses, fills the layer's address-table slots and encodes the expert pass and the rest of the layer, committed at layer end. After `131`, on all-hit layers: wake 43.6 us, CPU work about 10 us (id read 0.6, cache 1.5, expert encode 4.4, rest 3.6), commit to GPU start 115.8 us.

## Goals / Non-Goals

**Goals:** less GPU idle between router and expert pass, bitwise output, unchanged cache policy.

**Non-Goals:** speculative execution with rollback, GPU-side miss servicing, changing which experts are cached, MTL4 migration, changes to prefill sweeps or TP frames.

## Decisions

### D1. Gate

Measure the readback gap's components after `131`. The event-gated pass of D3 only removes CPU encode; close it if that is under 50 us per layer. Measured: about 8 us, closed.

### D2. Split the readback batch

On a single streaming box, `ds41_moe_partial` calls `ds4_gpu_split_readback()` after the router: the open batch (attention, router) is committed without waiting, and the next batch, holding the shared expert, is remembered. At the readback, if the open batch is that one, it is committed behind the pending command buffers and only those are waited (with `131`'s poll), then appended to the pending list with its cache sequence; otherwise the old full drain runs. Its transient buffers and model views are released at the next full drain, since it is still running. The remembered batch is a strong reference, so a stale value can never match a later batch. Cache in-flight sequences: the wait advances the done sequence to the router's batch, and the shared batch's sequence becomes the pending maximum, so no entry is marked done before its command buffer completes.

### D3. Rejected: event-gated pre-committed expert pass

Commit the expert pass before the ids are known, reading ids from the router's GPU buffer and addresses from the address table, behind a shared event the CPU signals after the cache check. A standalone probe: the GPU starts 102-105 us after the signal, the same as after a commit (103-107 us), so only the encode (about 8 us per layer) would be saved, at the cost of losing the resident/missing overlap on layers with three or more misses. A GPU kernel spinning on a CPU store in shared memory (or the reverse) would avoid the restart, but neither side sees the other's store until the kernel ends.

### D4. Rejected: optimistic continuation

The GPU running ahead with a miss flag and the token restarted from the first missing layer needs snapshots of every in-place state and costs a restart whenever any of 40 layers misses: 98.5% of tokens in short answers, 61% in long ones.

### D5. Evidence

`make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_READBACK_SPLIT` bitwise; harness `decode,append` with long and cold guards, `--bitwise`, hit rates equal; the per-step rule (under 800 runtime lines).

## Risks / Trade-offs

- The shared batch is pending across the readback -> its cache sequence and its transient buffers are carried until the next full drain.
- The split fires but the readback takes another branch (replay, override, validator) -> the next drain commits and waits both batches as before; the remembered batch no longer matches.

## Migration Plan

Branch `perf/132-gpu-all-hit-continuation`. The rollback switch stays as a decode control. No commit or push without a request.
