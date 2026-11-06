# Tasks

## 1. Baseline and tooling

- [x] 1.1 Count the chat-templated tokens of `speed-bench/promessi_sposi.txt`; confirm 72000 fits, else fix the frontier per design (Risks: prompt length) and update the spec scenario
- [x] 1.2 (dropped: the bench ran by hand, 5.4; the kind would need its own cache size, `82GB` does not fit at 81920, so the perf-harness delta is gone) Add `guard-long` to `speed-bench/ab_bench.py` (frontiers 40000, 72000; 64 tokens; context allocation 81920 for that kind only; joins `guards`) and to `speed-bench/README.md`
- [x] 1.3 Run upstream `b3f5018`'s `ds4-bench` at 40000 -> 72000 (`--ctx-alloc 81920`, `82GB`, `--dump-frontier-logits-dir`) and this child's sync tree with the same flags; keep both dumps as the reference, and record the admitted cache size and whether the logits already differ

## 2. Step 1: radix top-k select (`af7c02b` + `ff95f53`)

- [x] 2.1 Port the radix select kernels into `metal/argsort.metal` byte for byte and the dispatch into `ds4_gpu_indexer_topk_tensor_impl`, with the scratch reset of `ff95f53` and its V4.1-only gate
- [x] 2.2 Port the commits' kernel checks into `tests/test_deepseek41_metal.c`; classify `DS4_METAL_DISABLE_V41_TOPK_SELECT` in `ds4_env.def`; `make test` and `make test-deepseek41-metal` pass
- [x] 2.3 (replaced: the select starts at 16384 index rows, about 65K tokens, which the 65-token switch test never reaches, and it orders exactly tied scores by id, so the switch is not bitwise by design; `check_topk_select` compares it with the merge ladder at 16K-256K keys, and the 72000 logits equal upstream's) `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_TOPK_SELECT` passes
- [x] 2.4 Review the step (child rules, AGENT.md idiom); fix only what makes it wrong

## 2b. Step 1b: decode top-512 (`4ff3af6`)

- [x] 2b.1 Port the shuffle block sort, the prefix merges and `kernel_topk_select_sort512` into `metal/argsort.metal` byte for byte, and the decode-k512 dispatch, with `DS4_METAL_DISABLE_V41_DECODE_TOPK` classified in `ds4_env.def`
- [x] 2b.2 Port `check_decode_topk`; `make test-deepseek41-metal` and `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_DECODE_TOPK` pass
- [x] 2b.3 `ab_bench.py --kinds decode --bitwise` against the step-1 tree: the step must not lose at typical sizes
- [x] 2b.4 Review the step

## 3. Step 2: candidate-block scoring (`2d5ef0d`)

- [x] 3.1 Port the candidate scorer kernels (`metal/dsv41.metal`, `metal/dsv4_misc.metal`), `ds4_gpu_dsv41_indexer_candidates_tensor` with its `ds4_gpu.h` declaration, the `block_list` graph buffer, and the early return in `ds41_attention_select_published` past layer 20 above 2048 blocks
- [x] 3.2 Port its kernel checks; add a switch (upstream's name if it has one) restoring the full scoring; `make test`, `make test-deepseek41-metal` and that switch's decode-switch test pass
- [x] 3.3 Review the step

## 4. Step 3: exact wide scorer (`4b1b151` + `4f80638`)

- [x] 4.1 Port the wide scorer kernel with `fp contract(off)` and the FP4-only gate, and its dispatch from 8192 rows in `ds4_gpu_glm_indexer_score_one_tensor` ahead of rows4, as upstream orders it
- [x] 4.2 Port its kernel checks (wide == reference bits); add a switch restoring rows4/one-row scoring; tests pass as in 3.2
- [x] 4.3 Review the step

## 5. Verification

- [x] 5.1 Rerun the 40000 -> 72000 bench with the full change; every logits dump is byte-identical to upstream `b3f5018`'s (task 1.3). If not, bisect by step with each step's switch
- [x] 5.2 At the harness frontiers below 32K (2048, 8192, 16896) the logits equal the sync tree's (no change below 32K)
- [x] 5.3 `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from StarForge passes against `b3f5018`
- [x] 5.4 (bench ABBA by hand, the harness has no guard-long kind yet) `ab_bench.py --guards guard-long` against the sync tree, `--output-change` (the 72K output changes by design); a large loss is reviewed with the owner before landing
- [x] 5.5 (independent review: one latent row-copy bug, also upstream's, fixed; nothing made dead: `ds4_gpu_glm_indexer_score_one_tensor` stays as the rows4-only entry `tests/test_v41_indexer_score.c` checks, as upstream keeps both entries) Final review over the whole touched region against AGENT.md and the surrounding idiom; delete what the change made dead

## 6. Docs

- [x] 6.1 `docs/upstream-prs.md`: the five commits' rows become `adopt`, with the equality evidence; `AGENTS.md`: the new switches in the decode switch list
- [x] 6.2 `speed-bench/perf-record.md`: the guard row and the equality result
