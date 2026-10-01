# Design

## Context

See proposal.md and `docs/MacM5.md` sections 2-3. The packed MPP kernel uses an expert work list, independent output tiles, K=32 iterations, dequantized half staging and a cooperative float accumulator. There are already 64x32 and shape-gated 32x128 variants; this change does not invent a new baseline tile or assume a particular SLC size.

## Goals / Non-Goals

**Goals:** reduce redundant data movement into the active M5 matrix path, preserving every existing precision boundary.

**Non-Goals:** change prompt partitions, TP ownership, quantization, routing, K order, or revive #864's split-MPP variant. Dense decode belongs to `80`.

## Decisions

### D1. Measure the real shapes

After `80` is resolved, use `60`'s sections mode with `shared/routed ffn` and the cold/append shapes. Retain an uninstrumented A/A reading because section profiling serializes work. Attribute staging/barrier stalls and accelerator utilization with installed tools when available; do not install a toolchain or infer a utilization percentage from wall time alone. If the FFN section is no longer actionable, stop without kernels.

### D2. Expert-local traversal

First remap only independent output tiles. Within each expert, traverse token-row tiles and output-column tiles in a small locality-preserving block/Morton order. Do not interleave unrelated experts merely to draw a global Morton curve. Preserve work-list coverage, TP zero-fill behavior, tile dimensions, masked tails and the kernel's K loop. Use the existing work map; no additional host readback to discover its length. A model-less mapping check proves every legal tile appears once and only once, including irregular grids.

Alternative: tune tile dimensions at the same time. Rejected, because it confounds locality with arithmetic and register pressure.

### D3. Cooperative-input dequantization

As a separate step, obtain the TensorOps operand layout through its supported cooperative-input API and place the same half dequantized values there. Keep the existing descriptor and K=32 accumulation sequence. Retain the existing half-LUT decision from `60`; do not reinterpret IQ2_XXS as native INT2. The current threadgroup path remains the fallback on unsupported SDK/runtime combinations and shapes. If the API cannot express the old arithmetic bitwise, drop this step rather than change the numerical contract.

### D4. Paired MPP epilogue, conditional

Only after measuring register headroom, compute gate and up with two independent accumulators using the same descriptors. Apply the existing clamp, SwiGLU, route weight and intermediate cast at the same boundaries, then store the existing down-input layout. No FMA contraction across former rounding boundaries. It must beat the previous kept path on its own; a dropped D3 is not required scaffolding for this trial. Do not retain both implementations as user-selectable mathematical variants.

### D5. Validation and decisions

Extend the existing MoE prefill fixture rather than build another test framework. Compare dequantized operands, gate/up/mid/down values and logits bitwise at packed thresholds, full/partial expert tiles, repeated IDs, empty experts and TP ownership boundaries. Run `make test-metal-moe-prefill`, `make test-deepseek41-metal`, and the named model-less suite.

For a kernel-only gain below end-to-end resolution, use pooled section ratios per rows shape: target section / unaffected sections. Require a ratio CI below one on a target and above one on none, then run the normal `cold,append` harness as a guard. Scheduling changes do not qualify for this exception. Larger visible changes use the normal project step gate. Include timed decode evidence, long guards, final segment-start row and candidate-verified upstream parity.

## Risks / Trade-offs

- More registers lower occupancy -> measure each step; do not stack losing steps.
- Scatter and packed-row ordering mistakes -> sentinel/tile-coverage tests and intermediate byte comparisons.
- Compiler changes accumulation despite the same descriptor -> reject on the first bitwise discrepancy.
- New TensorOps calls unavailable on a supported build -> compile/runtime availability checks with the unchanged path; no host software upgrade.

## Migration Plan

One branch `perf/90-m5-prefill-tensor-locality`, after earlier proposals are resolved. Keep only measured variants, review the full touched region and dead code, update any acted-on PR verdicts, and document shape gates. No model conversion or persistent configuration. Commit/push remains a separate user action.
