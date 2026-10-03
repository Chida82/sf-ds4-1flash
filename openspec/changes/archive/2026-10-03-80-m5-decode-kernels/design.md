# Design

## Context

See proposal.md. `docs/MacM5.md` supplies hardware and GGUF facts; the timings in `speed-bench/perf-record.md` precede `70` and are not this change's baseline. The present dense kernel uses `FC_mul_mv_nsg` to partition K, so changing that value changes summation. `kernel_glm_indexer_score_one_direct` is live V4.1 code: 32 heads, 128 dimensions, one key row per threadgroup, dot/simd_sum plus ordered head accumulation.

## Goals / Non-Goals

**Goals:** improve the measured live decode kernels with the same per-output arithmetic; obtain a post-70 anatomy before estimating gains.

**Non-Goals:** more tokens per evaluation, fewer experts, alternative top-k ordering, approximate math, new quantization, global compiler changes, or optimizing a generic kernel that `70` has made irrelevant.

## Decisions

### D1. Baseline and start gate

Work on `perf/80-m5-decode-kernels` from the latest accepted child baseline after `60` and `70` are resolved. A rejected earlier step is not a missing dependency unless this design actually calls its API. Record A's identity and dirty state; keep A in a read-only-main worktree. Existing `DS4_METAL_ENCODER_TIMELINE` separates kernel groups without adding command-buffer waits, but adds pass serialization: use it for attribution, then measure normally without the probe. Keep `DS4_METAL_CB_TIMES` out of throughput runs.

At decode frontiers 2048/8192 and an additional 32768 diagnostic, identify actual kernel names, invocation counts, GPU duration, CPU gaps and expert read time. Implement a candidate only if its measured cost can exceed the current A/A resolution under an optimistic removal bound. No such cost means a documented no-op outcome.

### D2. Dense rows first

Target the post-70 Q8 matvec producers used for 1280-to-32768, 8192-to-5120 and grouped 4096-to-1024 projections; measure the vocabulary head separately. Compare a bounded set of output-row groupings (1, 2, 4). Retain the existing lane-to-K mapping, number of K-partitioning SIMDgroups, scale placement, FMA behavior, reduction and any fused BF16 store. Guard incomplete row tiles before weight access, not only at the output store.

This is preferable to an NSG sweep, TensorOps substitution or global weight repacking: those either change arithmetic or expand scope. Keep only the winning shape-specific dispatches and the ordinary fallback for other shapes/devices.

### D3. Indexer as an independent step

Evaluate processing a small group of independent key rows per threadgroup while keeping each row's four-SIMDgroup head progression and ordered accumulator. Reuse query loads where possible; do not replace the 32-head sum with a different parallel reduction. Compare score bytes, selected IDs/order and resulting logits, including all-zero and tied scores. If grouping requires a different reduction to become fast, drop it. Do not port #1061's rejected MMA scorer or #959 solely for a >128K workload outside the target mix.

### D4. Evidence and keep/drop

Kernel fixtures compare original and candidate paths in the same binary, including odd output tails, nonzero offsets, signed zero, cancellation-prone finite sums and existing exceptional-value cases. Whole-model `--bitwise` A/B uses `decode,append` as targets and `cold` plus the two long guards, split into bounded invocations as necessary. Guard deterioration is investigated with timed pairs, not dismissed from one noisy sample.

Each step is judged against the previous kept state under the project acceptance rule, with a short correctness review before timing. No neutral additive specialization stays. Final evidence compares to the performance segment start, reports the normal harness row, and includes upstream parity against the actual candidate checkout. A parity script resolving a sibling instead is a stop, not a valid pass.

## Risks / Trade-offs

- Register pressure from additional rows -> profile occupancy and keep the grouping bounded.
- Compiler reorders arithmetic after a layout change -> bitwise fixtures plus frontier/logit comparison, not a tolerance.
- Kernel improvements hidden by streaming -> require decode throughput evidence, not a standalone matvec score.
- Shared helpers affect TP, resident or vision callers -> keep unsupported shapes on the existing path and test caller-visible behavior; model-backed distributed runs require separate approval.

## Migration Plan

Trial switches are diagnostic only. Select one measured default per supported shape, remove failed candidates, and keep compatibility fallbacks. No new CLI or data migration. Rollback reverts this change without undoing `70`. Build Metal and separate CPU binaries, verify named tests, run the existing eval/parity gates, and record outcomes before any separately requested commit or push.
