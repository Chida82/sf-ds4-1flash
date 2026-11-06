# Design

## Context

- `f0b4f55` (upstream `ds4.c`, gate `logits && g->rope_tab && g->tp_world == 1
  && !g->streaming && !g->quality && !layer_resident ...`): builds one cos/sin
  table per token and fuses the index-query RoPE with its FP4 quantize. This
  child runs separate RoPE and quantize steps on the index query, on the 8
  index-source layers.
- `26335c7` (gates `g->scalar_decode && g->tp_world == 1 && !g->quality &&
  !g->streaming && !g->imatrix`, and a Metal check refusing streaming):
  computes the attention and FFN hyper-connection weights alongside the
  projections. It builds on the one-dispatch HC block input this child has
  since `70`, but the child has no deferred mixer.
- The streaming decode token of this child waits on the CPU for the router's
  selected ids (`131`/`132`/`210`); the shared expert already runs in that
  window.
- Measured context: decode is bound by expert reads (about 20 t/s steady), and
  sub-millisecond kernel savings have repeatedly fallen below the harness
  (perf-record, rejected ideas).

## Goals / Non-Goals

**Goals:**
- A cheap yes/no per candidate before porting.
- Bitwise output for anything ported.

**Non-Goals:**
- Lifting `!g->streaming` guards wholesale.
- `be2773b`, `57df7a5`, `565db43` (dropped, see the proposal).

## Decisions

- **Pre-screen with a scratch micro-bench.** The kernels each candidate
  removes or moves are timed on this machine in a scratch tree, using the
  `DS4_METAL_*_SOURCE` swap, with no harness run. The gate is a saving of at
  least 0.5% of a decode token (about 0.25 ms), since smaller savings have
  measured neutral. *Alternative:* port and A/B directly. It spends hours on
  candidates that upstream never measured.
- **`f0b4f55` FP4 check first.** Its fused RoPE + quantize is the same kind of
  fusion that can round an FP4 midpoint differently since `97e3276`. Run the
  midpoint comparison before timing; if it is not bitwise, drop it.
- **`26335c7` FFN half in the readback window.** Upstream's placement needs a
  concurrent level streaming does not have. The readback window is idle GPU
  time already, so the work moves there. The scratch the weights write
  (`g->x`, `g->flat_norm`) is checked against the split-deferred miss stage
  before porting.
- **One A/B for whatever passes.** `ab_bench.py --kinds decode,cold-2500
  --bitwise`; the intake rule applies.

## Risks / Trade-offs

- **[Both screens fail]** Likely, given the expected sizes. -> The change ends
  at stage 0 with two rejected-ideas rows and the registry updated; that is a
  valid outcome.
- **[Scratch overlap under misses]** Moving the FFN weights into the readback
  window could overwrite data a pending miss reads. -> The switch test runs
  with a small cache so tokens miss.
