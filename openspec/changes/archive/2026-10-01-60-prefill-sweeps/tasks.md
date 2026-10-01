# Tasks

## 1. Branch and base tree

- [x] 1.1 From a clean `main` (`2c733ca`):
  - `git switch -c perf/60-prefill-sweeps`;
  - `git worktree add --detach ../sf-ds4-1flash-base main`, point its `deepseek-v4.1-flash.gguf` symlink at the same blob as the checkout's, and run `make -j8` in it.

  Verify: `git status --short --branch` shows only this change's `openspec/` files, and the base tree's bench exists.

## 2. S1a: one sweep where main batches the tail

- [x] 2.1 Port the `ds41_prefill_count` half of `798c64f`'s net state (design D2), with `ds41_short_sweep_off` and the tail tested against the pos > 0 minimum. Update `tests/test_deepseek41_prefill.c`'s expected counts and add D2's schedule simulation.

  Verify:
  - `make -j8` has no warnings;
  - `make test` names `test_deepseek41_prefill` among its tests;
  - the simulation fails when the tail test uses the pos-0 minimum (check by a scratch edit, then revert it).
- [x] 2.2 (Kept. Invocation 1: inconclusive, every 3500/7500 pair dropped on cache drift; 5000 +0.1%, append +0.5%/+0.5%, bitwise. Invocation 2 with `--cache-policy-change`: `ttft 3500` +79.3% [+70.8, +81.7] n=8, `ttft 7500` +39.4% [+38.1, +40.2] n=20, bitwise; first-token details -1.5% and -3.9%, colder decode cache, inside ttft.) Short review of the step (AGENT.md, the child's rules, the `DS4_METAL_DISABLE_V41_SHORT_SWEEP` switch). Then A/B against the base per design D7, pooled over two invocations.

  Verify:
  - correctness PASS (bitwise) at 3500, 5000 and 7500;
  - `ttft 3500` and `ttft 7500` pooled CI above zero, and no throughput CI wholly below zero;
  - the rows are saved under `scratch/60-s1a-*`.

  If dropped, revert 2.1 and go to 3 with the base unchanged.

## 3. S1b: the decoder suffix below 8192

- [x] 3.1 Port `798c64f`'s `ds41_graph_prefill_sweep` hunks (`suffix_rows`, the tile-rounded `first`, 128 warm rows, the skip when `first` is 0). Apply S1a's diff to the base tree and rebuild it (design D1).

  Verify: `make -j8` has no warnings, and `make test` names its tests.
- [x] 3.2 (Kept, one invocation: `ttft 3500` +2.6% [+1.7, +4.1] n=11, `ttft 5000` +2.2% [+1.6, +3.0] n=12, `ttft 7500` +30.2% [+29.7, +30.3] n=10, bitwise; guards neutral: decode 2500 -0.4%, 16896 +0.6%, n=1.) Short review, then A/B against the S1a tree per D7, with `guard-16896` added.

  Verify:
  - bitwise at every cold frontier;
  - the D7 targets pass the keep rule.

  A bitwise failure is a drop, recorded as `drop: output` with the frontier.

## 4. S2: prefill index batching

- [x] 4.1 (Kept, one invocation; it deletes one line and adds none, so even neutral it stays: `ttft 2500` +0.6% [+0.3, +1.1] n=8, `ttft 3500` +1.0% [-1.0, +2.5], `ttft 5000` +0.4% [+0.2, +1.0], `ttft 7500` +2.3% [+0.1, +5.4], `ttft 10000` +1.2% [-1.1, +1.9], bitwise; guard decode -0.6% n=1.) S2a, `1011874`: remove the `ratio == 2u` gate in `ds41_attention_batch`. Base tree = previous steps.

  Verify:
  - `make -j8`;
  - `make test`;
  - `make test-deepseek41-metal` passes;
  - A/B on `cold` per D7, bitwise, keep rule.
- [x] 4.2 (Kept, two invocations pooled: `ttft 7500` +1.69% [+0.77, +3.26] n=12; 2500 +0.62% [-0.30, +1.32], 3500 +0.09% [-0.85, +1.50], 5000 +0.13% [-0.18, +0.44], 10000 +0.43% [-0.87, +2.59]; bitwise. Review: in prefill only `candidate_filter` at layers > 20 reads `block_mask`, and it is skipped for exactly the rows whose mask is skipped; the child's per-row `top = min(blocks, 2048)` equals 2048 on every row the batch keeps.) S2b, `ce5a812`: upstream text for `ds4.c`, `ds4_metal.m`, `ds4_deepseek41_gpu.h`, `metal/dsv41.metal` and `tests/test_deepseek41_metal.c`. First, record in the short review where `block_mask` is consumed, and that rows below 16385 × ratio never read it (design D4).

  Verify:
  - `make -j8`;
  - `make test`;
  - `make test-deepseek41-metal` names the new candidate-batch cases;
  - A/B on `cold`, bitwise, keep rule.
- [x] 4.3 (Kept, one invocation: `ttft 7500` +4.3% [+3.3, +9.7] n=6; 2500 +1.3% [-0.1, +3.2], 3500 +0.9% [-4.2, +2.1], 5000 -0.2% [-2.5, +0.5], 10000 -0.6% [-2.9, +1.3]; bitwise. Review: selection order is irrelevant, the batched indexed attention sorts ids (`ds4_indexed_topk_sorted`); rows under 512 keys take the all-keys path.) S2c, `3b7f8f2`: upstream text, including `kernel_dsv41_indexer_all` and its test.

  Verify:
  - `make -j8`;
  - `make test`;
  - `make test-deepseek41-metal` names the select-all case;
  - A/B on `cold`, bitwise, keep rule.

## 5. S3: explicit expert buffers

- [x] 5.1 (`bac91c2` + `c12d639` runtime text from `c12d639`, minus `imatrix` and the pre-M5 gate; no tail-cull kernels. The four upstream tests are model-less, so `make test` runs `--prefill-expert-discard` and `--prefill-expert-stream`, which also runs admission and fd. `make cpu` builds. A cold-2500 bench prints the explicit-buffer line, admission 74.88 GiB and 8078 slots, prefill 77.7 t/s.) Port `bac91c2` + `c12d639` per design D5:
  - the buffers, readers, binding, release and F_NOCACHE descriptor;
  - no tail-cull kernels, no device gate;
  - the `test_deepseek41_graph.c` I/O, admission and fd cases.

  Verify:
  - `make -j8` has no warnings;
  - `make test`;
  - `tests/test_deepseek41_graph --prefill-expert-stream` passes, with the other ported flags;
  - a cold-2500 bench run prints the "two explicit layer buffers" line;
  - its admission line shows 74.88 GiB and 8078 slots.
- [x] 5.2 (Kept, one invocation: `ttft 2500` +14.2% [+13.7, +15.1] n=12, `append +1500` +42.6% [+36.0, +43.5] n=10, bitwise, cache counters equal; `append +300` -0.17% [-0.30, +0.03], a token-major append S3 does not reach; guard decode +1.1% n=1, no decode loss. Review: readers only `pread`, Metal calls stay on the encoding thread; free joins, drains, detaches, unlocks and discards on every path.) Short review (cancellation and release paths, the reserve admission, no Metal call off the encoding thread). Then A/B per D7.

  Verify:
  - bitwise;
  - `ttft 2500` or `append +1500` pooled CI above zero;
  - `decode` guard and first-token details not wholly below zero.

  If decode drops, run the sub-step without `c12d639`'s descriptor (design Risks) before deciding.

## 6. S4: sections mode and kernel steps

- [x] 6.1 (A/A of the S3 tree on `cold-2500`, 22 pairs: `sections 2048 rows` 0.43, -0.4% [-1.8, +2.1], bitwise; `python3 tests/test_ab_bench.py` 41 tests OK, `test_section_ratios` and `test_sections_flag` new.) S4.0, tool step: `--sections` in `speed-bench/ab_bench.py` (design D6), `tests/test_ab_bench.py` cases for the parser and the ratio, and `speed-bench/README.md`.

  Verify:
  - `python3 -m unittest tests/test_ab_bench.py` names the new tests;
  - one invocation of the S3 tree against itself with `--sections "attention core/index"` reports bitwise and a ratio CI across one.
- [x] 6.2 (Dropped and reverted: sections A/B against S3, bitwise, `attention core/index` share at 2048 rows (`cold-2500`) -2.0% [-3.6, -0.7] n=24, i.e. slower, while 1452 rows (`cold-3500`) +3.0% [+0.8, +4.5] and 2048 rows there +1.4% [-5.9, +4.1]; a ratio above one at one shape drops it. ttft 2500 +1.9% [+0.1, +2.6], ttft 3500 -0.0%.) S4a, #758 `a3393d7`: the `heads16_dual_rb16` kernel, its pipeline and the gate only.

  Verify:
  - `make -j8`;
  - `make test-deepseek41-metal`;
  - sections A/B on `attention core/index`: ratio CI below one at a targeted shape and above one at none;
  - one `cold` harness run as the guard, bitwise.
- [x] 6.3 (Dropped and reverted: sections A/B against S3, bitwise, `shared/routed ffn` share at 2048 rows (`cold-2500`) -3.8% [-4.1, -2.9] n=29 and at 1452 rows (`cold-3500`) -2.4% [-3.1, -1.0], i.e. slower; only 2048 rows in `cold-3500` +8.5% [+2.6, +11.6]. The exhaustive table check (`metal/check_iq2xxs_half_lut.py`, 2048 entries, caught a one-bit corruption) went with it.) S4b, #864 half LUT in `dequantize_iq2_xxs`, with an exhaustive model-less dequant equality test added to `make test`.

  Verify:
  - the test names every code checked;
  - sections A/B on `shared/routed ffn` per the rule;
  - one `cold` harness run as the guard, bitwise.

## 7. Close

- [x] 7.1 (Nothing made dead: both S4 steps reverted whole. Kept upstream text, including `798c64f`'s getenv switch and `c12d639`'s `#if defined(__APPLE__)` descriptor guard, to keep the sync sites small; the only deviations are D2's pos > 0 minimum and the prefill_cap / carry_cap guards, and S3's dropped `imatrix` and pre-M5 terms. No refinement with a speed claim.) Final pass over every touched region against `AGENT.md` and the surrounding idiom: delete what the outcomes made dead, and check that nothing drifted from upstream text without a reason. A refinement with a speed claim is measured like a step.

  Verify:
  - `make -j8` has no warnings;
  - `make test` names its tests;
  - `make test-deepseek41-metal` and `make test-metal-ssd-experts` pass.
- [x] 7.2 (Against `7dea5e3`, so it carries `30` and `40`: 19 valid pairs, bitwise, exit 0; ttft 2500 +26.1%, 3500 +91.0%, 5000 +13.4%, 7500 +85.2%, 10000 +3.2%, append +300 +10.9%, +1500 +44.2%, guard decode +14.7%, guard 16896 +8.6%, e2e +10.8%. Decode kinds not run, no step touches decode; the guard reads 21.2 t/s, `40`'s band.) Record row:
  - `git worktree add --detach ../sf-ds4-1flash-start 7dea5e3` (gguf symlink, `make -j8`);
  - the final tree against it with `--kinds cold,append --guards guard-decode,guard-16896 --bitwise`;
  - paste the row into segment 1 of `speed-bench/perf-record.md`, with each step's pooled rows.

  Verify: the row's decode columns are within the A/A noise of the `40` row.
- [x] 7.3 (Registry: the seven #1073 commits, #952 `bac91c2`/`c12d639`, #758 moved to `a3393d7` as history, #864 history; #850/#822 unchanged. `AGENTS.md`: the prefill schedule paragraph and switches. `perf-record.md`: step table, row and note. `speed-bench/README.md`: `--sections`.) Docs and registry per design D8.

  Verify: `grep -n "1011874\|ce5a812\|3b7f8f2\|ccbf2c0\|64240fb\|798c64f\|4fbbc4a\|bac91c2\|c12d639\|a3393d7\|482e246" docs/upstream-prs.md` shows the new verdicts, and nothing else in the registry changed.
- [x] 7.4 (`PARITY OK (10 prompts)`, token-identical to upstream `0aaea5a`; child speed +11.6..+36.2% per prompt.) Closing parity from the StarForge checkout: `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`.

  Verify: `PARITY OK (10 prompts)`.
- [x] 7.5 (Scope: this change's code, tests and docs, plus the owner's own commits on the branch (`docs/MacM5.md`, `docs/ssd.md`, `speed-bench/iobench.c`, changes 80-150); worktrees removed; validate passes.) Scope check.

  Verify:
  - `git diff main --stat` lists only files named in the proposal's Impact, plus docs and this change's `openspec/` files;
  - `git worktree list` shows only the checkout after the worktrees are removed;
  - `openspec validate 60-prefill-sweeps --strict` passes.
