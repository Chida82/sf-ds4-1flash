# Design

## Context

Per decode layer on a single streaming box today (`ds41_moe_partial`, `ds4_gpu_routed_moe_one_tensor`):

1. attention and router are encoded into batch A; `ds4_gpu_split_readback()` commits A without waiting and remembers the next batch;
2. the shared expert is encoded into that batch S;
3. at the readback, `ds4_gpu_commit_split_wait_pending()` commits S, waits every older pending command buffer (A, and B of the layer before) with `131`'s 2 ms `cb.status` poll, then `ds4_gpu_tensor_read(selected)` copies six ids out of a shared buffer;
4. `ds4_gpu_begin_commands()`, cache peek, miss loads, the expert pass and the rest of the layer go into batch B, flushed at layer end; A of the next layer is encoded while B runs.

`132`'s probe on this tree, all-hit layers: wake 43.6 us after A's GPU end (the status turns `Completed` about 45 us after the GPU ends, `131`), id read 0.6 us, cache peek 1.5 us, expert encode 4.4 us, commit to B's GPU start 115.8 us, GPU idle before B 121.6 us. The decode token is 38-44 ms, 40 layers.

The expert cache tracks in-flight entries with sequences: a batch gets a sequence when created, `g_stream_expert_cache_pending_max_seq` holds the highest committed one, and `ds4_gpu_wait_pending_command_buffers` advances `g_stream_expert_cache_done_seq` to it after waiting the whole list. An entry whose `inflight_seq` is above the done sequence is skipped by the victim scan.

## Goals / Non-Goals

**Goals:** learn the ids when the router's command buffer ends on the GPU rather than when its status says so; bitwise output; cache policy and hit rates unchanged; rollback to the `131`/`132` path by one switch.

**Non-Goals:** the next-layer prediction mailbox (`145`/`170` closed prediction), a GPU-side wait, pre-committed expert passes (`132` D3), changes to prefill, TP frames, the Q4 shared-event path, or the resident graph.

## Decisions

### D1. Gate: visibility latency (measured)

A standalone probe (a busy kernel of about 400 us, then a one-thread kernel storing ids, checksum and sequence into a shared buffer; the CPU spins with `yield`, 400 iterations; the encoder is serial) gave, medians:

| Layout | flag seen after the CB's GPU end | status `Completed` after the GPU end |
|---|---|---|
| publish last in the CB | 20.6 us (p90 21.4) | 47.9 us |
| publish, then 80 us more work, same encoder | 20.7 us after the CB end | 47.9 us |
| publish, then a new encoder with that work | 20.7 us after the CB end | 48.3 us |
| publish ends the CB, the work in the next CB | 19.5 us (p90 20.2) | 47.1 us |

Without `yield` the flag is the same and the status later (55 us). No checksum mismatch in 3200 records. The gate (median below 35 us) is open, but the probe overturns the original premise: the store is published by the command buffer's end, not the kernel's, so the shared expert cannot follow the publish in the router's command buffer without delaying the ids by its own duration. `132`'s split therefore stays and the mailbox replaces only the wait on A.

The decode batch's encoder is serial (`ds4_gpu_compute_encoder` opens a concurrent encoder only inside the explicit parallel-FFN and kv-task sections, neither of which encloses the router), so the publish sees the router's stores without a barrier; the publish is skipped when a concurrent section is open.

### D2. Publish kernel

`kernel_dsv41_selected_publish` (`metal/dsv41.metal`): one thread, `constant uint2 &args` (sequence, n), `device const int32_t *selected`, `device uint *box`. It stores the ids at `box[2..2+n)`, an integer checksum of the sequence and the ids at `box[1]`, then the sequence at `box[0]`. The CPU accepts a record only when `box[0]` is the armed sequence and the checksum agrees. The box is a 64-byte `MTLResourceStorageModeShared` buffer created at first use and released at cleanup.

`ds4_gpu_split_readback(selected, n)` encodes it as A's last dispatch when n is at most 8, the encoder is serial and `DS4_METAL_DISABLE_V41_READBACK_MAILBOX` is unset (read at every call, so the decode-switch test can toggle it in one process), then commits A as today and arms the mailbox with A, A's cache sequence, the tensor and n.

A separate kernel rather than a store folded into `kernel_dsv41_router_one`: the router kernel is shared with prefill rows and must stay exact; folding saves one dispatch and can be a refinement if the harness can see it.

### D3. Readback by mailbox

`ds4_gpu_commit_split_wait_pending(selected, ids, n)` commits S as today. When the mailbox is armed for the same tensor and n, it polls the box (spin with `yield`, bound 20 ms) instead of waiting. On a hit it returns 2 with the ids, and the readback site skips `ds4_gpu_tensor_read`; cache peek, loads and the expert pass follow unchanged. On a timeout it counts a fallback and takes today's path (wait every pending buffer, tensor read): a fallback stays bitwise and only loses the overlap. The streaming summary prints `selected-id mailbox hits=... fallbacks=...`.

The mailbox applies only to this readback; replay, override, validator and the full-address-table branches are untouched.

### D4. Pending command buffers

On a hit, A is still pending (its status is not `Completed` yet). Every buffer committed before A is waited: B of the previous layer and anything older ended before A started, so in practice the wait returns at once, and it is the same wait as today for the buffers whose expert-cache entries matter. They leave the list, and the cache's done sequence moves to A's sequence minus one: every batch created before A was committed before it, and owned buffers finish synchronously. A holds attention and the router, no expert-cache entry; were one marked there it would stay in flight one layer longer, never shorter. If A is no longer in the list (a full wait drained it), everything pending was waited and the done sequence moves to the pending maximum, as `ds4_gpu_wait_pending_command_buffers` does. A and S stay pending with S's sequence as the maximum; the next full wait settles them. Transient buffers and model views are released at full drains as with `132`.

### D5. Evidence

- `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_READBACK_MAILBOX`: 65 tokens at two positions, logits, Engram history and KV state bitwise against the `132` path.
- `test-metal-ssd-experts`, `--stream-decode-queue-parity` (decode under cache eviction), `test-metal-command-memory`.
- A CLI decode with `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1`: hits and fallbacks.
- Harness `decode,append` with the long and cold guards, `--bitwise`, hit rates equal, against the previous kept tree; the per-step rule (well under 800 runtime lines).
- `make cpu` builds; parity oracle at the end.

## Risks / Trade-offs

- Visibility is an observed property, not a documented one -> the sequence and checksum reject torn records, the bounded poll falls back to the waited path, and the fallback counter is printed.
- A fallback costs nothing beyond the spin it replaces: it happens when A really is still running (seen once per process, the second readback after a prefill, with A behind about 100 ms of queued work).
- The CPU spins per layer as `131` does; the bound keeps a stalled GPU from pinning a core for more than 20 ms.

## Migration Plan

Branch `perf/210-decode-router-mailbox`. The rollback switch stays as a decode control and joins the list in `AGENTS.md`. Provenance (Argodrive `9ad4a61`) goes in `docs/upstream-prs.md` and the commit message, not in source comments. No commit or push without a request.
