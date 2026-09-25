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
layers. That is a fact `40`'s pool statistics establish on this machine, not
one that can be assumed.

A related finding in the child: the consumer
`ds4_gpu_glm_stream_selected_prefetch_take` (`ds4_metal.m:16091`, called at
`:33493`) can never fire. Its producer,
`ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor`, was removed with
the GLM graph; in main it was called only from GLM code. This is a "name that
lies": #952 `a3043bb2` uses that GLM-named producer for V4.1.

## What Changes

- **Start gate.** This change starts only if `40` shows a shallow read queue,
  or an idle SSD between layers, in the decode and `append` kinds. Otherwise
  it closes with those numbers, and the dead consumer is deleted as an
  ablation (`sf-ablate(glm)` marker at the call site).
- **S1.** #952 `a3043bb2`, early-load part only:
  - restore the producer and its prefetch set from main (`ds4_metal.m`
    ~17221-17340), keeping upstream's name;
  - add a row to the "Names that lie" table in `AGENTS.md`;
  - hook it in `ds41_moe_partial` after routing (about 14 lines).

  Its BF16-with-RoPE fusion is **not** taken here: the glue belongs to the
  `70` code zone, and there is one PR per zone. This step comes after `40`
  S1, because early loading changes when cache slots are reserved.
- **S2, conditional.** Port #849 to V4.1:
  - register the F32 router;
  - drop the hash-layer and GLM hunks;
  - keep the staging buffers and the retain mark.

  At about 800 lines, in doubt, it needs at least +1.5% decode. The retain
  mark changes hit counts by design, so S2 reports them instead of gating on
  them. The logits must still be bitwise identical.
- **Not taken:** the rest of #952 `a3043bb2` (rounding fusion, see above).

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
