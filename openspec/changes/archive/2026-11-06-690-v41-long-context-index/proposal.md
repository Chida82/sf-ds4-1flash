# Proposal

## Why

The `b3f5018` sync kept this child's own decode graph and ported upstream commits
one by one. Five merged upstream commits (all through #1073) change how the
V4.1 sparse-attention indexer picks its key blocks beyond about 32K tokens of
context, and the sync left them open. Without them this child no longer
matches upstream's greedy output at those lengths. Since 2026-11-05 the parity
oracle is judged against the current upstream, so an upstream commit that is
merged and changes the output is taken for alignment, not dropped (the old
`drop: output` rule applies to unmerged PRs only). `5382eac`, the medium-append
sweep that the registry listed as their predecessor, landed in the sync.

## What Changes

- Port `af7c02b` + `ff95f53`: select the indexer's top-k candidates with a
  radix select on Metal, with its scratch reset when the row count changes
  and limited to V4.1. Upstream's switch `DS4_METAL_DISABLE_V41_TOPK_SELECT`
  comes with it.
- Port `4ff3af6` on top of that: the decode top-512 (a shuffle block sort and
  prefix merges that keep only the first 512, `kernel_topk_select_sort512`),
  with upstream's switch `DS4_METAL_DISABLE_V41_DECODE_TOPK`. Its gate needs
  the radix select (`radix && n_tokens == 1 && top_k == 512`). It runs from
  about 2K tokens of context, so unlike the other commits it reaches the
  typical 1-10K workload; it returns the same indices in the same order, so
  the output there does not change.
- Port `2d5ef0d`: index layers after layer 20 score only the candidate blocks
  that can be selected when the compressed context has more than 2048 blocks
  of 8 (about 64K tokens at ratio 4).
- Port `4b1b151` + `4f80638`: a wide index scorer with one thread per key from
  8192 index rows (about 32K tokens at ratio 4), with exact arithmetic
  (`fp contract(off)`) and an FP4-only gate.
- These are hand ports. Upstream hooks them into
  `ds41_attention_select_published` and `ds4_gpu_dsv41_indexer_score_one_tensor`.
  This child decodes through its own graph and scores through
  `ds4_gpu_glm_indexer_score_one_tensor` with the rows4 scorer (`345d7f4`).
- Measure the long regime with the bench by hand (40000, then 72000), A B B A.
  A harness guard kind for it is left out: at 81920 of context the `82GB`
  cache does not fit, so it would need its own cache size, and no other
  change measures there yet.
- **BREAKING (output)**: greedy output changes for contexts above about 32K
  tokens and becomes upstream `b3f5018`'s. The project context's "output
  never changes" rule is the conflict this change resolves: the owner decided
  that parity follows the current upstream.

## Capabilities

### New Capabilities
- `long-context-index`: how the V4.1 decode indexer chooses and scores key
  blocks once the compressed context is long, its agreement with upstream, and
  the switches that restore the earlier paths.

### Modified Capabilities
None.

## Impact

- Code: `ds4.c` (indexer call sites in the V4.1 decode graph, graph buffers),
  `ds4_metal.m` (top-k select, candidate scorer, wide scorer dispatch),
  `metal/argsort.metal`, `metal/dsv41.metal`, `metal/dsv4_misc.metal`,
  `ds4_gpu.h`, `ds4_env.def`.
- Tests: `tests/test_deepseek41_metal.c` (kernel checks from the commits),
  model-backed decode-switch tests, and logits equality against upstream at
  long frontiers.
- Tooling: `speed-bench/ab_bench.py` (one guard kind) and its README.
- Docs: `AGENTS.md` (switch list), `docs/upstream-prs.md` (the five rows),
  `speed-bench/perf-record.md`.
- Runtime: the output changes only above about 32K tokens, the guard
  scenarios of this child's workload (typical prompts are 1-10K tokens). The
  decode top-512 of `4ff3af6` runs from about 2K tokens, with unchanged output.
