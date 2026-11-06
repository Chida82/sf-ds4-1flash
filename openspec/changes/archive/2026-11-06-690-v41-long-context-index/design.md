# Design

## Context

See proposal.md for why. The relevant state of this child after the `b3f5018` sync:

- Decode selects attention blocks in `ds41_attention_select_published` (`ds4.c`).
  For each index-source layer it projects the index query (from the exact E4M3
  copy when built), applies RoPE, FP4-quantizes it and computes the head
  weights. It then scores every compressed key with
  `ds4_gpu_glm_indexer_score_one_tensor`, whose dispatch picks the rows4
  kernel of `345d7f4` when it can. `ds41_attention_pick` follows:
  `ds41_attention_candidates` builds the layer-20 block mask, and later layers
  filter with it; then a full `ds4_gpu_indexer_topk_tensor` sort runs.
- Upstream `b3f5018` has the same function names in the same places, with the
  five commits applied. Its scorer entry is `ds4_gpu_dsv41_indexer_score_one_tensor`;
  this child keeps the older `glm_` name (see AGENTS.md, Names that lie).
- What each commit changes:
  - `af7c02b`: replaces the top-k sort with a radix select inside
    `ds4_gpu_indexer_topk_tensor_impl` (`ds4_metal.m`, `metal/argsort.metal`).
  - `ff95f53`: resets that select's scratch when the row count changes.
  - `2d5ef0d`: adds `ds4_gpu_dsv41_indexer_candidates_tensor`, which scores and
    selects in one pass over the candidate blocks only, plus a `block_list`
    graph buffer. Past layer 20 above 2048 blocks it returns early from
    `ds41_attention_select_published`.
  - `4b1b151` + `4f80638`: add a wide one-thread-per-key path to the scorer
    dispatch from 8192 rows. It is exact (`fp contract(off)`) and FP4 only.
- Nothing measured here so far reaches these lengths. The harness allocates a
  32768-token context, and its longest guard is 16896.

## Goals / Non-Goals

**Goals:**
- Bitwise logits equality with upstream `b3f5018` at 40K and 72K frontiers.
- Every new path behind a switch that restores the previous one bitwise. Where
  upstream has a switch, use its name.
- No change below 32K tokens, verified by unchanged logits at the existing
  harness frontiers.

**Non-Goals:**
- Prefill-side long-context work (`23c333b`, `01772c0`). They stay
  `history: long` in the registry. `64ceeea` is decode-side (long index rows
  scored from bf16 views of the FP4 keys), but exact by construction, so it
  does not decide the equality. Ported and measured on top as `740`: neutral,
  dropped (perf-record, rejected ideas).
- Raising the 32768 context the harness allocates for every other kind.
- Tuning the new kernels beyond upstream's. A refinement pass may follow if
  the guard shows a loss.

## Decisions

- **Port in upstream's order, three steps and a decode top-512 step.** Step 1
  is `af7c02b` + `ff95f53`, step 1b is `4ff3af6` (it needs step 1's `radix`
  plumbing), step 2 is `2d5ef0d`, step 3 is `4b1b151` + `4f80638`. Step 1b
  is the only one that reaches contexts under 32K, so it is also measured on
  the typical kinds (`decode`, which allocates 2048 and 8192). Each step brings its
  kernel test from `tests/test_deepseek41_metal.c` and is judged on its own.
  `ff95f53` fixes `af7c02b`, so they are one step. The order matches upstream,
  so the logits equality of each step against an upstream commit between them
  can localize a mismatch. *Alternative:* one combined step. It is cheaper, but
  a mismatch at 72K would then have three suspects.
- **Port upstream's final state, not each commit's.** `b3f5018` no longer has
  `4ff3af6`'s non-causal shuffle block sort, and later commits reshaped the
  top-k host code. Every kernel and host block is taken as `b3f5018` has it,
  so the equality oracle compares like with like. The steps stay as the order
  of work and of review.
- **Keep this child's call structure; copy upstream's kernels verbatim.** The
  host code goes into `ds41_attention_select_published` and
  `ds4_gpu_indexer_topk_tensor_impl`, which both trees still share. Kernels are
  copied byte for byte so their bits are upstream's. *Alternative:* merge
  upstream's whole decode select function. That would undo the E4M3 index
  query and the rows4 dispatch.
- **Scorer dispatch order equals upstream's.** At 8192 rows and more, with
  FP4 keys, the wide scorer wins, as upstream decides; rows4 stays below that.
  Both are exact, so the order affects speed only. Following upstream keeps
  that decision reviewable against its source.
- **Equality oracle: the bench, not the parity CLI.** Both binaries run with
  `--ctx-start 40000 --step-incr 32000 --ctx-max 72000 -n 16
  --dump-frontier-logits-dir` and a context allocation of 81920. The
  `b3f5018` sync used the same method for `5382eac`. The parity CLI runs one
  short `-p` prompt and cannot reach these lengths.
- **Measurement: a long guard, not a timed kind.** Contexts above 10K tokens
  are guard scenarios in this child's workload policy. The bench runs 40000,
  then 72000, by hand as A B B A (`60GB`: `82GB` does not fit next to 81920 of
  context); the planned `guard-long` harness kind was left out for that
  reason. Typical sizes are
  checked by bitwise logits, not by a speed run, because the code paths below
  32K do not change. *Alternative:* an ABBA timed kind at 72K. One run takes
  several minutes, which would spend the budget on a scenario outside the
  typical mix.
- **Upstream switch names.** The step 1 switch is
  `DS4_METAL_DISABLE_V41_TOPK_SELECT`. Steps 2 and 3 take upstream's switch
  names where they exist, else new `DS4_METAL_DISABLE_V41_*` names classified
  in `ds4_env.def`.

## Risks / Trade-offs

- **[Prompt length]** The benchmark prose may not hold 72000 tokens after the
  chat template. → Check its token count first. If it is short, take the
  frontier from the largest multiple of 8 blocks above 65536 that fits, and
  note it in the spec scenario.
- **[Memory at 81920 context]** Static context buffers grow with ctx: about
  8 GiB at 32768, so roughly 20 GiB at 81920. This leaves less room for the
  82GB expert cache under the wired limit. → Run the guard with the same cache
  flag. If the loader caps the cache, record the admitted size, and compare A
  and B only under equal admission (the harness's cache check).
- **[Upstream bits depend on fused paths this child lacks]** Equality might
  fail for a reason outside the five commits, such as a resident-only path.
  → Bisect with the step-wise comparison, and compare against upstream with
  the matching switch where one exists. If the cause is outside these
  commits, stop and report.
- **[Time]** Each 72K comparison prefills about 72K tokens twice in streaming
  (several minutes per binary). → Keep the oracle to the two frontiers and
  run model-backed checks once per step.

## Migration Plan

The change lands like any other change: one signed commit on main after its
review passes. Rollback is the switches (bitwise to the previous paths) or a
revert of that commit. Users see different greedy output only above about 32K
tokens, and that output is upstream's.
