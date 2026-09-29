# Design

## Context

See proposal.md (Why). Facts from the code and the diffs:

- **The decode MoE today** (`ds4.c` `ds41_moe_partial`): the router matmul and
  `router_select` are queued, then the shared expert's three matmuls, then
  `ds4_gpu_routed_moe_one_tensor`. That function reads the selected ids back
  (`end_commands` or the shared-event wait, then `tensor_read`), which waits
  for the router *and* the shared expert, then prepares buffers and preads the
  missing experts on the calling thread while the GPU is idle, then queues the
  routed kernels.
- **The consumer is already in the child.** `routed_moe_one_tensor` first asks
  `ds4_gpu_glm_stream_selected_prefetch_take` (`ds4_metal.m` ~16423, called at
  ~33835) for ids read earlier; on a match it takes them as `prefetched`,
  finishes the pending load and flushes the shared expert's work. The struct
  `g_glm_stream_selected_prefetch` is there too. Only the producer is missing:
  `ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor` and
  `ds4_gpu_glm_stream_selected_prefetch_set` (upstream `0aaea5a`
  `ds4_metal.m` 17221-17330, about 110 lines, and one declaration in
  `ds4_gpu.h`). The producer ends the batch, reads the ids, starts the pending
  load (`begin_selected_load`: buffers prepared, preads queued on the pool
  without waiting), records the ids for the consumer and reopens the batch.
- **#952 `a3043bb2`'s hook** calls the producer in `ds41_moe` right after
  `router_select`, before the shared expert, under `streaming && !quality &&
  tp_world == 1`, a configured cache and the IQ2_XXS/Q2_K expert types. In the
  child the site is `ds41_moe_partial`; there is no `imatrix` field. The same
  commit fuses BF16 rounding into RoPE: not taken (the `70` zone).
- **What S1 can hide.** The readback now waits for the router only; the preads
  run on the pool while the GPU computes the shared expert (three matmuls of
  one row) and while the CPU encodes it. The sync moves, it does not grow. The
  gain per layer with a miss is at most the shorter of the shared expert's GPU
  time and the pread; the buffer preparation stays serial before the preads.
  Four layers of a token have a miss (`40`'s Read path), so the bound is well
  under 1 ms of a 50 ms token.
- **#849 `60051d4`** (923-line diff): a background thread scores layer L+1's
  router (`sqrt(softplus(W h)) + bias`) on layer L's router input and
  pre-reads the top guesses into staging buffers, plus a retain mark. As
  written it registers F16 routers only (V4.1's `ffn_gate_inp` is F32) and the
  hash-router hunk does not apply (V4.1 has none). Its own numbers: 46% of
  misses covered at 0.4 wasted reads per useful one; -5.5% on plain GGUF reads
  (bandwidth-bound), +5.2% only with #848.
- **After `40`** the pool splits each read in four on 18 threads, and the
  slabs are in a residency set. The Read path figures (pread 2.1 ms, buffer
  preparation 2.0 ms per decode token at 2K) were taken before those, so S0
  measures them again.

## Goals / Non-Goals

**Goals:**
- The bound on this change, measured on `main` as it is now.
- The early load of `a3043bb2`, bit-identical, kept only if the harness sees
  it; otherwise the dead consumer goes.
- A recorded, numeric verdict on #849 without porting 800 lines that cannot
  reach their threshold.

**Non-Goals:**
- `sync` itself (GPU work: `70`), the buffer preparation's cost (a
  child-written change; recorded as a candidate if S0 shows it large),
  the replacement policy (`45` candidate), the prefill sweeps (`60`).
- TP, `--quality`, and non-Q2 expert types: the hook's guard keeps them on
  the current path.

## Decisions

### D1. Three steps

- **S0, diagnosis, no code.** On `main` (`b044217`), the bench with
  `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1 --cache-stats` at frontier 2048
  with 16 and 256 generated tokens, at 8192 with 256, and `cold-5000`; decode
  figures by difference, as in `40`'s Read path. Recorded as a second table
  in that section: pread, buffer preparation and `sync` per decode token and
  per tail step, and the pool line.
- **S1, early load.** The producer and its `_set` restored verbatim from
  upstream `0aaea5a` (upstream's names; `DS4_METAL_DISABLE_GLM_STREAMING_
  EXPERT_EARLY_LOAD` is its switch), its declaration in `ds4_gpu.h`, and
  `a3043bb2`'s hook in `ds41_moe_partial` minus the `imatrix` term. A row in
  AGENTS.md's "Names that lie": the `glm_stream_*` early-load pair is the V4.1
  decode's producer and consumer. Measured against `main`.
- **S2, conditional.** Opens only if `0.46 × pread_per_decode_token ≥ 2 ×
  0.015 × token_ms` with S0's figures (at 50 ms: 3.3 ms of pread). Then the
  port of `60051d4` (F32 router, no hash or GLM hunks, staging buffers and the
  retain mark), with at least +1.5% on `decode 8192` to keep. Otherwise
  closed as history in the registry with S0's numbers.

Alternative: port #849 first, as the larger potential. Rejected: its own
measurement lost 5.5% without #848, its ceiling here is a fraction of about
2 ms, and it costs a CPU thread and wasted reads.

### D2. Keep rule and metrics

As in `40`: targets `decode 8192`, `append +300` (token-major append) and
`ttft 5000` (sweep plus a 904-token tail); kept when one target's pooled 95%
CI lies above zero over two invocations and no throughput metric's lies
wholly below; a first invocation with all three targets at or below zero is a
drop. S1's retain-free change must keep the cache counters equal between A
and B; a drift is a bug here, not a policy change.

### D3. Invocation shape

`--kinds decode,append,cold-5000 --guards guard-decode --bitwise --budget
2700`. S1 runs `--a ../sf-ds4-1flash-base` (a worktree of `main`) `--b .`.
No `--quality` CLI run precedes an invocation (the page-cache trap of `30`).

### D4. Correctness

- `--bitwise` on every invocation.
- `DS4_METAL_DISABLE_GLM_STREAMING_EXPERT_EARLY_LOAD=1` on the S1 tree gives
  the same tokens as `main` on one CLI prompt (the switch restores the old
  path), and the harness's cache counters are equal.
- `make test`, `make test-metal-ssd-experts`, parity at the end.

### D5. Docs and registry

Registry: #952 `a3043bb` (adopted early load, or history with the numbers),
#849 `60051d4` (history with S0's bound, or the port's numbers). AGENTS.md:
the "Names that lie" row if S1 is kept, the switch among the knobs.
`perf-record.md`: S0's table, the rows, the change's row against the segment
start. If S1 is dropped: `sf-ablate(glm)` at the consumer's call site and the
consumer and struct deleted.

## Risks / Trade-offs

- [The gain is below what the harness resolves] → two pooled invocations;
  an honest drop and the dead code removed is an acceptable outcome.
- [Moving the readback before the shared expert changes when slots are
  reserved, relative to `40`'s in-flight seeds] → equal cache counters and
  bitwise output; `make test-metal-ssd-experts`.
- [The producer's pending load stays active if the consumer does not match]
  → the consumer compares every table field and the producer clears `active`
  at entry; a mismatch falls back to the normal readback. Reviewed in S1.
- [Sync conflict] → upstream's text for the producer, the hook at one site.

## Migration Plan

Additive; the switch restores the current path. Rollback is a revert of the
squash commit.

## Open Questions

- Whether S2 opens: S0's pread figure decides it, by the formula in D1.
