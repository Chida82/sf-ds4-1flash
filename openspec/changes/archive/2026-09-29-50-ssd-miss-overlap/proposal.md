# Proposal

## Why

A decode layer learns which experts it needs only after the router runs and
the six ids are read back. Only then does it read the missing experts, and it
waits for them. Two PRs start those reads earlier:

- **#952 `a3043bb2`** issues the miss reads right after routing, overlapping
  them with the shared-expert projections. It was measured only on an M1 Max
  (2.43 -> 2.44-2.50 t/s).
- **#849 `60051d4`** runs layer L+1's router on layer L's input in a
  background thread and pre-reads the predicted experts into staging buffers.
  It measured +5.2% on an M4 Max, but only on top of #848, and −5.5% without
  it, when bandwidth-bound. As written it is inert on V4.1: it registers only
  F16 routers (V4.1's `ffn_gate_inp` is F32) and relies on hash layers (V4.1
  has none).

Both pay only if the reads are latency-bound and the SSD sits idle between
layers. `40` measured it (`speed-bench/perf-record.md`, Read path): the pool
runs at `qd_avg` 2.2, so the queue is shallow, but the reads are small. A
decode token spends about 2 ms in pread and 2 ms in buffer preparation out of
52 ms; the 38 ms of `sync` are GPU work and no overlap of reads touches them.
So this change can recover at most about 4 ms a token (8%), and each PR only a
part of that: `a3043bb2` hides a layer's pread behind that layer's shared
expert, `60051d4` at most the 46% of misses its forecast covers.

A related finding in the child: the consumer
`ds4_gpu_glm_stream_selected_prefetch_take` (`ds4_metal.m:16091`, called at
`:33493`) can never fire. Its producer,
`ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor`, was removed with
the GLM graph; in main it was called only from GLM code. This is a "name that
lies": #952 `a3043bb2` uses that GLM-named producer for V4.1.

## What Changes

- **Start gate.** Met: `40` showed a shallow queue (`qd_avg` 2.2).
- **S0, diagnosis.** The Read path measurement again on `main` after `40`
  (split 4, 18 threads, slab residency): pread and buffer preparation per
  decode token and per token-major tail step. It sets the bound of S1 and the
  gate of S2.
- **S1.** #952 `a3043bb2`, early-load part only:
  - restore the producer and its prefetch set from main (`ds4_metal.m`
    ~17221-17340), keeping upstream's name;
  - add a row to the "Names that lie" table in `AGENTS.md`;
  - hook it in `ds41_moe_partial` after routing (about 14 lines).

  Its BF16-with-RoPE fusion is **not** taken here: the glue belongs to the
  `70` code zone, and there is one PR per zone. This step comes after `40`
  S1, because early loading changes when cache slots are reserved.
- **S2, conditional.** It opens only if 0.46 of S0's pread per decode token
  is at least twice 1.5% of the token (the forecast's coverage against the
  800-line threshold, with a factor two for its wasted reads and its CPU
  router); at 50 ms that is 3.3 ms of pread a token. Otherwise it closes as
  history with S0's numbers. Port #849 to V4.1:
  - register the F32 router;
  - drop the hash-layer and GLM hunks;
  - keep the staging buffers and the retain mark.

  At about 800 lines, in doubt, it needs at least +1.5% decode. The retain
  mark changes hit counts by design, so S2 reports them instead of gating on
  them. The logits must still be bitwise identical.
- **Not taken:** the rest of #952 `a3043bb2` (rounding fusion, see above).
- **If S1 is not kept**, the dead consumer is deleted as an ablation
  (`sf-ablate(glm)` marker at the call site).

## Capabilities

### New Capabilities
None. Output is bitwise identical (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m` (the stream-cache prefetch producer and consumer), and `ds4.c`
  `ds41_moe_partial`.
- S2 adds a CPU thread that runs a 384×5120 F32 multiply per layer, staging
  RAM, and about 0.4 wasted reads per useful one. The measurement must show
  that the extra reads do not slow the Engram reads or the demand reads.
- Registry lines: #952 `a3043bb2`, #849.
