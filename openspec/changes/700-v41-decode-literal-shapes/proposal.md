# Proposal

## Why

Upstream `b3f5018` carries five merged commits the `b3f5018` sync left as
"streaming candidates" (`docs/upstream-prs.md`): `b66c926`, `4ff3af6`,
`e99dc21`, `a50fecc` + `04c0867` and `0f9b03c`. A read of each against this
child's streaming decode on the M5 Max found that only part of them is
reached here:

- `b66c926` compiles V4.1's fixed decode shapes into its matvecs. Two of its
  four kernels run on every decode layer of this child: the paired q_a/kv
  projection (`ds4.c` `ds41_attention`, host gate `in_dim == 5120 && out_a ==
  1280 && out_b == 512 && nr0 == 2`) and the output-B expand (`rows == 1`,
  8192 -> 5120, no add). The MXFP4 MoE literal is unreachable (the experts are
  IQ2_XXS/Q2_K) and the FFN-join literal runs only with
  `DS4_METAL_DISABLE_V41_EXPAND_FUSION`.
- `e99dc21` spreads two single-core reductions. Its Engram-gate half
  (`kernel_dsv41_engram_add_tg256`, `width == 5120 && rows <= 16`) is reached;
  its collapse half requires `!g->streaming` and code this child does not have.
- `4ff3af6` (decode top-512) is reached from about 2K tokens of context, but
  its gate needs the radix select of `af7c02b`, so it joins change `690`.
- `a50fecc` + `04c0867` touch only the plain Q8 matvec, which V4.1 decode
  barely uses, and are proven bitwise on M1 Max only. `0f9b03c` is M3 Ultra
  only or shadowed by the packed scorer on M5. Both are dropped.

Upstream claims both kept parts are bitwise and gives no M5 figure. This
change takes them, measures them together, and keeps them only if the
measure clears the intake rule.

## What Changes

- Port from `b66c926` the q_a/kv pair literal
  (`kernel_mul_mv_q8_0_f32_bf16_pair_qa_kv`) and the output-B expand literal
  (`kernel_mul_mv_q8_0_f32_bf16io_hc_expand4_static`), with upstream's switch
  `DS4_METAL_DISABLE_V41_LITERAL_SHAPES`.
- Port from `e99dc21` the 256-thread Engram gate kernel, with upstream's
  switch `DS4_METAL_DISABLE_V41_SPLIT_REDUCE`, only if it is bitwise on this
  machine (its exactness rests on matching the compiler's fma contractions).
- Record `4ff3af6` under change `690`, and `a50fecc`, `04c0867`, `0f9b03c`
  and the unreachable halves as dropped in `docs/upstream-prs.md`.
- No output change.

## Capabilities

### New Capabilities
- `decode-literal-shapes`: V4.1 decode kernels specialized to the model's
  fixed shapes, their exactness, and the switches that restore the generic
  kernels.

### Modified Capabilities
- None.

## Impact

- Code: `metal/dense.metal`, `metal/dsv4_hc.metal`, `metal/dsv41.metal`,
  `ds4_metal.m` (dispatch gates), `ds4_env.def` (two switches).
- Tests: kernel checks adapted from upstream's `check_literal_shapes` and
  `check_engram` in `tests/test_deepseek41_metal.c`;
  `make test-deepseek41-decode-switch` with each switch.
- Docs: `AGENTS.md` decode switch list, `docs/upstream-prs.md`,
  `speed-bench/perf-record.md`.
- Runtime: every decode token; the expected gain is small (a few dispatches'
  worth of index arithmetic per layer), so the A/B decides.
