# Design

## Context

A decode layer on a single streaming box, today (after `132` and `210`):

```
GPU: [attention + router + publish] [shared expert]  ....idle....  [routed pass + rest of layer] [attention L+1 ...
CPU:              commit ^   commit ^  poll mailbox -> ids -> cache -> encode routed + rest -> commit ^
                                       |<--------- GPU idle before the routed pass ------------->|
```

The `132` probe (decode 2048, 256 tokens, split tree, before the mailbox) put the idle at 121.6 us on an all-hit layer: wake 43.6, ids 0.6, cache 1.5, expert encode 4.4, rest encode 3.6, commit to GPU start 115.8. The mailbox sees the ids about 20 us after the router batch's GPU end instead of 45-48 us. What remains is mostly the restart of an idle GPU after a commit, which neither a commit nor a CPU-signalled event shortens (`132` D3). A batch committed while the GPU is still busy starts about 1 us after the previous one (`130` D3).

What already exists and this design reuses:
- Per-layer address tables (`g_stream_expert_cache_{gate,up,down}_addr_buffers`, one 64-bit GPU address per expert). An entry is set when an expert is installed in the cache and zeroed when it is cleared.
- The masked expert kernels, `kernel_mul_mv_addr_iq2_xxs_pair_swiglu_masked_f32` and `kernel_mul_mv_addr_q2_K_sum6_masked_f32`. They take the ids from a GPU buffer and an active-slot mask, read each expert's address from the table and skip an address of 0. The `145` split runs the resident pairs, then the missing pairs, then one down over all six (`active_mask = 0x3f`, `accumulate = 0`). The down sums the six experts in one pass whatever the split, and that pass is what keeps the split bitwise.
- The GPU hit validator, `kernel_stream_expert_cache_validate` (`DS4_METAL_ENABLE_STREAMING_EXPERT_HIT_VALIDATOR`, a probe). It compares the selected ids against the tables on the GPU.
- The selected-id mailbox (`210`) and the router committed on its own, with the shared expert in the next batch (`132`).

## Goals / Non-Goals

**Goals:** no GPU restart between the router and the routed pass on all-hit layers; miss layers no slower than today; bitwise output; the same cache bookkeeping in the same order (hit rates equal).

**Non-Goals:** running ahead more than one layer, GPU-side miss servicing or eviction, changes to which experts are cached, prefill sweeps, the TP path, MTL4.

## Decisions

### D1. Gate (S0): three measurements before any code

Each is a gate. The change closes at the first that fails, with a rejected-ideas row.

Measured: closed at gate 1 (`perf-record.md`, "Expert pass ahead of the ids after 675"). The Context above holds for `132`'s tree, not today's. Since `210`, the CPU commits the routed batch about 25 us before the shared batch drains, and the GPU starts it 2.3 us (p50) after. All-hit layers therefore have no restart left to remove: their gaps are 0.3-0.5% of decode, against the 2% gate.

1. **Ceiling: the all-hit idle on today's `main`.** Re-measure, per layer, the GPU idle before the routed pass and its components on all-hit and miss layers, and the all-hit share, at decode 2048 and 8192. A temporary probe in a scratch tree stamps the CPU's return from the mailbox poll and each commit against the command buffers' GPU times; `132`'s probe is gone, and nothing of it lands. The projection is all-hit idle times all-hit layers per token, over the token time. Close if it is under 2% of decode, about twice the decode A/A spread.
2. **Window: does one layer of lead hide the CPU?** On all-hit layers, compare the GPU time queued behind the router batch (shared expert plus routed pair and down, from `DS4_METAL_CB_TIMES` or the encoder timeline) with the CPU's reaction: router batch GPU end, then mailbox seen, then the next batch committed (bookkeeping, plus the encode of the rest of the layer and of the next attention and router). The design needs the reaction's p90 below the window's p10. If it is not, re-project measurement 1 with only the hidden part, and fall back to D6's halt variant only if that one's own probes pass.
3. **Feasibility: GPU-side state alone, same kernels.**
   - Confirm that all-hit layers today run the masked pair and the masked sum6 with `active_mask = 0x3f`. The pre-committed pass then uses the same pipelines and arguments, and is bitwise by construction.
   - Confirm that the pass's encode needs no host-side ids. The open point is whether the per-expert slot buffers must be bound or used by the encoder, or whether the slab residency set of `40` already makes every slot resident.
   - Run decode with the hit validator and count the disagreements between "address non-zero" and the CPU's hit decision. Include the first tokens after a prefill, because prefill's selected-address path points table entries at model-mapping overflow views (`ds4_gpu_stream_expert_cache_set_addr_slot` from the batch selected-address code).
   - Close if the pass cannot run on the same pipelines without host ids, or if the table cannot be made exact at decode time.

### D2. The routed pass committed ahead of the ids

When the streaming split path is ready (`ds4_gpu_stream_expert_split_ready`, single box, masked address-table pipelines present), `ds41_moe_partial` encodes the routed pass into the shared-expert batch, right after the shared expert: the masked pair (`0x3f`), then the masked sum6 (`0x3f`, `accumulate = 0`). It reads the ids from `g->selected` and the addresses from the layer's tables, so it is committed together with that batch, before the readback. At the readback the CPU polls the mailbox, does the cache lookups and bookkeeping exactly as today, and on an all-hit layer encodes nothing for the routed pass. It goes on to the rest of the layer and the next layer's attention and router, whose batch is committed at the next router while the routed pass is still running:

```
GPU: [attn+router+publish] [shared + routed pass] [rest L + attn L+1 + router L+1 + publish] [shared + routed L+1] ...
CPU:          commit ^  commit ^   poll -> ids -> cache -> encode rest L, attn L+1 -> commit ^ (before the GPU drains)
```

Alternatives:
- Gating the pass on a CPU event (`132` D3): rejected, because a signal restarts an idle GPU no faster than a commit.
- Putting the pass in its own batch: one more commit per layer, for nothing.

### D3. Miss layers

The CPU learns of the misses from the mailbox ids and the cache lookup, and loads them as today (pread pool, `145` early start). In the meantime the pre-committed pass has computed the resident pairs, which is `145`'s resident stage, and a partial down over the resident experts only, since a missing expert's address is 0. Before writing a loaded expert's address into layer L's table, the CPU waits until the pre-committed batch has completed. That batch finishes in about 0.2 ms against a load of about 1 ms, so the wait is normally free. It also guarantees the pass never reads a half-loaded slot and never computes a missing expert twice. The next batch then carries the missing pairs (the missing mask) and the down over all six (`0x3f`, `accumulate = 0`), which overwrites the partial down. That is today's `145` sequence, so the bits are the same.

The victim of a load is never one of layer L's selected experts. That is today's rule, re-checked in S0.3. No other layer has a routed pass in flight, so an eviction cannot touch one. The cache's in-flight sequences move with the batch: the shared-expert batch's sequence now also covers the slots the routed pass reads, so none of them is marked done before that batch completes (`210` D4).

### D4. Cache policy unchanged

The same lookups, hotness and recency updates and decay, in the same order, still at the readback. Only the encode of the routed pass moves. The harness checks that hit rates are equal.

### D5. Scope

Single-box Metal SSD streaming decode once the split is ready, which also covers the token-major prefill tails that run the decode graph. Everything else keeps today's path: TP, resident mode, `--quality`, the first decode tokens before the split is ready, and the replay and override branches of the readback. The rollback switch `DS4_METAL_DISABLE_V41_EXPERT_PASS_AHEAD` restores today's encode.

### D6. Alternatives not taken

- **Optimistic continuation with rollback** (`132` D4): it needs snapshots of every in-place state and restarts the token on any miss (98.5% of tokens in short answers). Here nothing runs past an unresolved layer.
- **Halt at the first miss.** The GPU runs the whole token ahead, and the work after a missing layer is turned off by a halt flag or by zero-threadgroup indirect dispatches. It would also remove the CPU from all-hit layers, but every dispatch after a router would need an indirect form or a halt check inside kernels shared with upstream. It is considered only if gate 2 shows that one layer of lead cannot hide the reaction. Its own probes are the cost of an empty indirect dispatch on M5 and the number of dispatches per layer, which sizes the turned-off tail.
- **Upstream's opt-in full expert address table** (`DS4_METAL_ENABLE_STREAMING_FULL_EXPERT_ADDR_TABLE`, "gpu-full-addr"). It has no readback, but it addresses every expert in the model mapping instead of the cache, so it takes the page faults that SSD streaming exists to avoid, and it turns off the streaming layer batch. It is not measured here and not the target.

### D7. Evidence

- `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_EXPERT_PASS_AHEAD` bitwise, including a run that starts after a prefill sweep, so that miss layers are covered.
- The streaming-cache, decode-queue and command-memory tests, reading the names of the tests that ran.
- Harness `decode,append` with the long and cold guards, `--bitwise`, hit rates equal, against the previous kept tree, under the project's keep rule. The change is expected under 800 runtime lines.
- After it, the idle and window figures of gates 1-2 again, to show where the time went.

## Risks / Trade-offs

- [The CPU reacts slower than the queued GPU work on some layers, for example on the parked CPU cluster that `220` saw] → Gate 2 measures the distribution, not the mean. The partial gain is re-projected, and the mailbox poll already keeps the decode thread spinning on a warm core.
- [Table entries that point outside the cache during decode, such as prefill overflow views left behind] → The pre-committed pass would read through the model mapping. The bytes are correct but page-faulted, and the CPU would also count a miss. Gate 3 counts these cases; the fix is to clear such entries when the sweep ends, before decode, inside this change.
- [A wasted partial down on miss layers, about 4 a token] → It runs while the miss loads, when the GPU would otherwise wait. It costs time only if a load ever finishes first, which would show as a lower append or decode-after-sweep figure in the A/B.
- [Batches carried across the readback hold transient buffers and cache sequences longer] → The same mechanism as `132`'s shared batch, extended to one more pass. The command-memory test covers it.
- [Encode order changes in `ds41_moe_partial`, which is shared with the token-major tails] → The tails take the same path and are in the harness's `append` kinds.

## Migration Plan

Branch `perf/680-expert-pass-ahead`, worktree `.claude/worktrees/680-expert-pass-ahead`. The rollback switch stays as a decode control. If a gate fails, the change is archived with its figures in the performance record and a rejected-ideas row. No commit or push without a request.
