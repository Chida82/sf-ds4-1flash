# Tasks

Every A/B in this list runs against the previous kept step, as design D4
sets out: `--bitwise --budget 3600 --kinds decode,append,cold-2500
--guards guard-decode`, with `cold-5000` added from S4g on. Its rows are
saved under `scratchpad/70-<step>-*`. Every step that is decided gets its
registry line in `docs/upstream-prs.md` and its pooled row in
`speed-bench/perf-record.md` in the same group, kept or dropped.

## 1. Branch and base tree

- [x] 1.1 From a clean `main` (`0d88af9`):
  - `git switch -c perf/70-decode-glue-fusions`;
  - `git worktree add --detach ../sf-ds4-1flash-base main`, point its
    `deepseek-v4.1-flash.gguf` symlink at the checkout's blob, and run
    `make -j8` in it;
  - check that `refs/sfpr/1073` is at `3d3c83b`.

  Verify: `git status --short --branch` shows only this change's
  `openspec/` files, and the base tree's bench exists.

## 2. S0: the decode control test (tool)

- [x] 2.1 Port `a3f6f31`'s `check_decode_control` into
  `tests/test_deepseek41_graph.c`:
  - `ssd_streaming = true`, and the prompt read with the test file's own
    reader;
  - the `ds41_route_batch` signature change only if S2 needs it, otherwise
    left out;
  - a `test-deepseek41-decode-switch` make target taking `SWITCH=` and the
    `speed-bench/promessi_sposi.txt` prompt.

  Verify:
  - `make -j8` has no warnings;
  - `make test` names its tests;
  - `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_DECODE_FLUSH`
    prints `65 exact logits/history/KV states PASS` for prefixes 511 and
    2047;
  - with a scratch edit that perturbs one decode `ds41_bf16` only while the
    switch is unset, it fails; the edit is then reverted.
- [x] 2.2 Record S0 as a tool step (test only, no runtime line): the
  `a3f6f31` registry line, and the `AGENTS.md` model-backed checks line for
  the target.

  Verify: `git diff main --stat` lists only the test, the Makefile and
  docs.

## 3. S1: candidate selection skipped while every block is kept

- [x] 3.1 Apply `e768396`. Short review: up to 2048 blocks the filter is
  the identity, and no reader consumes the skipped mask.

  Verify:
  - `make -j8`;
  - `make test`;
  - `make test-deepseek41-metal` passes.
- [x] 3.2 A/B against the base tree, then update the registry and the
  record.

  Verify:
  - correctness PASS (bitwise);
  - `decode 2048` or `decode 8192` pooled CI above zero and none wholly
    below zero, or a neutral step that deletes more lines than it adds.

  If dropped, revert 3.1.

## 4. S2: experts in one dispatch

- [x] 4.1 Apply `edceb7a` (kernel text from `3d3c83b`, design D2). Then
  add the router equivalence test to `tests/test_deepseek41_metal.c`:
  router one against `ds4_gpu_router_select_tensor` on forced ties, an
  all-equal round, all logits at -120, ±0 and denormal logits, comparing
  ids and weights bitwise.

  Verify:
  - `make test-deepseek41-metal` names the router cases and passes;
  - a scratch edit that swaps the tie order makes it fail, then is
    reverted.
- [x] 4.2 Run `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_ROUTER_ONE`.
  Then A/B, then update the registry and the record.

  Verify:
  - decode-switch PASS;
  - harness bitwise;
  - the keep rule on the decode targets.

## 5. S3: rounding inside the producing kernels

- [x] 5.1 Port `d95f8b6`'s Metal kernels and entry points (head text, D2)
  and its single-row `ds4.c` sites:
  - `ds41_matmul` Q8_0 BF16, `ds41_norm`;
  - the `_bf16` HC weighted sum and expand;
  - `ds4_gpu_dsv41_rope_bf16`;
  - the bf16io output and shared-down projections;
  - `ds4_gpu_hc_expand_split_add_bf16_tensor` in `ds41_graph_after_moe`
    on one box.

  Prefill call sites stay as they are, and TP keeps its branch. Short
  review against `d95f8b6` site by site.

  Verify:
  - `make -j8`;
  - `make test`;
  - `make test-deepseek41-metal`.
- [x] 5.2 A/B, then update the registry and the record.

  Verify: bitwise, and the keep rule.

## 6. S4: the `d8d1523` sites

Each site below is ported per design D2:
- head kernel text;
- the single-token call site with its fallback;
- no `_rows` call site;
- `sf-ablate(dspark)` where a DSpark branch is cut.

Each site then gets a short review, `make -j8`, `make test` and
`make test-deepseek41-metal`, and the decode-switch run for its switches
(D3). Then comes the A/B, then the registry line and the record row. Any
failed verify is a drop: the site is reverted and the next site's base
stays unchanged. Each site's runtime line count is recorded with its
verdict.

- [x] 6.1 S4a, HC block input: `ds4_gpu_dsv41_hc_block_input`,
  `_hc_project`, `_hc_input` and the M5 cluster2 variant, called from
  `ds41_hc_mix(..., pre)` for both HC blocks.

  Verify:
  - decode-switch PASS for `DS4_METAL_DISABLE_V41_HC_BLOCK_INPUT` and
    `DS4_METAL_DISABLE_M5_HC_NORM_MIX_CLUSTER2`;
  - harness bitwise;
  - the keep rule.
- [x] 6.2 S4b, attention projections: `ds4_gpu_dsv41_project_pair_q8`,
  `_norm_pair` and `_project_q`, wired through
  `ds41_attention_project(..., rope_il, &roped)`.

  Verify: harness bitwise, and the keep rule.
- [x] 6.3 S4c, rope store: `ds41_rope_store` and
  `ds4_gpu_dsv41_rope_quantize` with `1923131`'s `fma`, for the window, the
  index and the compressed rows. Also take `c6f4086`'s rope-quantize case
  in `tests/test_deepseek41_metal.c`.

  Verify:
  - the rope-quantize case passes bitwise against rope + quantize;
  - harness bitwise;
  - the keep rule.
- [x] 6.4 S4d, staged attention: `ds4_gpu_dsv41_attention_decode` and the
  flash head share in `metal/flash_attn.metal`, with the gather fallback.

  Verify:
  - decode-switch PASS for `DS4_METAL_DISABLE_GATHERED_KV_STAGE` and
    `DS4_METAL_DISABLE_FLASH_HEAD_SHARE`;
  - harness bitwise;
  - the keep rule.
- [x] 6.5 S4e, attention output into HC: `ds4_gpu_dsv41_attention_low`
  (inverse RoPE folded) and `ds4_gpu_dsv41_matmul_expand` for the
  attention output and for the shared down in
  `ds41_graph_after_moe(g, m, l, carry)`. Also `ds41_moe_partial`'s
  `shared_down` argument.

  Verify:
  - decode-switch PASS for `DS4_METAL_DISABLE_V41_EXPAND_FUSION`;
  - harness bitwise;
  - the keep rule.
- [x] 6.6 S4f, shared SwiGLU: `ds4_gpu_dsv41_shared_swiglu` in
  `ds41_moe_partial`.

  Verify: harness bitwise, and the keep rule.
- [x] 6.7 S4g, asynchronous Engram and the F16 rounded projection:
  - `ds4_engram_read_batch_start/_finish` in `ds4_engram.c/.h`;
  - in `ds41_graph_step`, the start before the first command buffer and
    each join before the table's write at layer 1 and layer 14;
  - `ds4_gpu_dsv41_project_f16_bf16` in `ds41_matmul`.

  Short review: the cancellation and error paths join the reader, and the
  layer-13 drain precedes the second table's write.

  Verify:
  - `make test` names `test_engram`;
  - harness bitwise with `cold-5000` added;
  - the keep rule on the S4g targets.
- [x] 6.8 The cumulative check (design D4), if the kept S4 sites add up
  to more than 800 runtime lines: one invocation of the S4 tree against
  the S3 tree.

  Verify: `decode 2048` or `decode 8192` gains at least +1.5%. Otherwise
  drop the smallest kept sites until the rest passes, and record which
  ones went.

## 7. S5: the head before the last drain

- [x] 7.1 Port `4fbbc4a`'s head half: the vocabulary head encoded in the
  last layer's command buffer, so `ds41_graph_logits` does not open its
  own. The sweep half is already in `main` from `60`.

  Verify:
  - `make -j8`;
  - `make test`;
  - harness bitwise;
  - the keep rule on the S5 targets.

## 8. Close

- [x] 8.1 Final pass over every touched region against `AGENT.md` and the
  surrounding idiom:
  - delete what the outcomes made dead, such as fallbacks a kept site made
    unreachable on one box but TP still reaches: those stay;
  - check that kernel text matches `3d3c83b` except at marked cuts;
  - a refinement with a speed claim is measured like a step.

  Verify:
  - `make -j8` has no warnings;
  - `make test` names its tests;
  - `make cpu` builds;
  - `make test-deepseek41-metal` and `make test-metal-ssd-experts` pass.
- [x] 8.2 Record row: the final tree against the segment start
  (`git worktree add --detach ../sf-ds4-1flash-start 7dea5e3`, gguf
  symlink, `make -j8`) with
  `--kinds decode,cold,append --guards guard-decode,guard-16896 --bitwise`.
  Paste the row into `speed-bench/perf-record.md`.

  Verify: bitwise, exit 0, and the cold ttfts no lower than the `60` row's
  beyond the A/A noise.
- [x] 8.3 Closing parity from the StarForge checkout:
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`.

  Verify: `PARITY OK (10 prompts)`.
- [x] 8.4 Scope check.

  Verify:
  - `git diff main --stat` lists only files named in the proposal's
    Impact, plus `ds4_engram.c/.h`, docs and this change's `openspec/`
    files;
  - `git worktree list` shows only the checkout once the worktrees are
    removed;
  - `openspec validate 70-decode-glue-fusions --strict` passes.
