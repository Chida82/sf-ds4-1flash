# Tasks

> Paused 2026-10-28: blocked by the missing streaming path of the batched MoE. See `design.md`, "Status: paused".

## 1. Setup (scratchpad only)

- [x] 1.1 (2026-10-28, 1017 checkpoint, scratch clone `scratchpad/pr1073/ds4` at `cad7933`; cache line "effective 82.00 GiB = 7.12 GiB prefill headroom + 74.88 GiB dynamic cache (8078 experts)"; one cold 256-token run: prefill 6.48 t/s, generation 13.49 t/s, which includes the first token after a cold cache, so it is not a decode figure) Make a scratch clone of the upstream mirror at `pr/1073` (`cad7933`) in the scratchpad, without adding a worktree to the mirror, and build it. Verify: a plain greedy decode under `--ssd-streaming --ssd-streaming-cache-experts 82GB` at a 32768 context prints the admitted cache line and its tokens/s; record both.
- [x] 1.2 (2026-10-28, owner approved; the file is `DeepSeek-V4.1-Flash-DSpark.gguf`, 8 633 942 016 bytes, repo revision `57ddd58e`; header: `deepseek41-dspark`, `dspark.block_size` 5, target layers 37 38 39, markov rank 256, 128 experts top-3, hidden 5120, MXFP4 weights) With the owner approval, `hf download kernelpool/DeepSeek-V4.1-Flash-MXFP4-GGUF DeepSeek-V4.1-Flash-DSpark.gguf` into the shared cache. Verify with a stdlib GGUF header read: `dspark.block_size` 5, three stages, the target layers, and a hidden size matching the main model.
- [x] 1.3 (2026-10-28, FAILED under streaming, so D1 fallback applies to 3.x) Scratch patch: drop `g->streaming ||` from `ds41_draft_init`. Run `--dspark --mtp-model <file>` under streaming for 256 tokens. Verify there is no failure and the PR's acceptance counters print. On failure, record it and switch to D1's fallback for 3.x.

## 2. Output (D3)

- [ ] 2.1 Row level: dump the logits of every verify row for 64 cycles, and the one-row logits at the same positions from a plain run. Verify bitwise. If it differs, find the configuration that is bitwise (MMA rows off first) and record which switches it needs.
- [ ] 2.2 Token level: greedy 1024 tokens with and without `--dspark` on `tools/parity/sf-ds4-1flash.txt` and the four kinds (D2), in the configuration of 2.1. Verify identical tokens, or record the first differing position per prompt.

## 3. Verify cost (D4)

- [ ] 3.1 c(k) for k = 1..5 at 2048 and 8192, with forced length (cap k, confidence 0), split into GPU, waits and miss reads. Write `speed-bench/dspark-verify-curve.json` (D4). Verify that a plain run of the same binary gives t_decode within 2% of 1.1's, and that the file holds k = 0..5 at both frontiers.

## 4. Acceptance (D2)

- [ ] 4.1 For each kind at confidence 0.4, 0.6, 0.8 and caps 2, 3, 5: acceptance per position, mean accepted length, mean drafted k. Verify that each cell has at least 200 cycles, or note why.
- [ ] 4.2 The uncut cell per kind (confidence 0, cap 5) with `DS4_DSPARK_SPEC_LOG` captured to a file (D7b). Verify that every logged cycle has five confidences and an accepted length, and that at least 200 cycles per kind were logged.
- [ ] 4.3 Offline replay (D7b), in a scratchpad script: #1073's rule over the grid, the expected-cost rule from `dspark-verify-curve.json`, and the oracle, per kind; plus the calibration table per position. Verify the replay against the run: for the cells measured in 4.1, the replayed mean accepted length is within 5% of the measured one.

## 5. End to end

- [ ] 5.1 Plain against `--dspark` on one binary, ABBA, at least three quads per kind and frontier, with the default back-off and the best cap and confidence from 4.1. Report the medians and the pair-ratio CI. Verify that the prose arm shows whether back-off engaged (its skip counter).

## 6. Memory (D5)

- [ ] 6.1 The `225` timeline with the drafter beside `82GB` at a 32768 context. Verify zero swapouts and no compressed engine pages, and record the minimum available memory.
- [ ] 6.2 Replay the `225` decode dump with the cache shrunk by about 800 slots (and 430), and for unions of k+1 consecutive tokens. Verify that 8078 slots still reproduce 3.91 miss layers per token.

## 7. Decision

- [ ] 7.1 Project onto main by D6, and apply D7.
  - Write the `perf-record.md` section: setup, the tables of 2-6, the projection and the verdict.
  - In `docs/upstream-prs.md`, set the DSpark commit lines of #1073 to the decision.
  - Record the drafter file (D8) and the default cap and confidence.
  - Record the draft-length rule `330` S4 starts from (D7b), with its replayed gain and the calibration verdict.

  Verify that every D7 condition is quoted with its number. If a condition needs the owner (output, prose tolerance, code at +10..25%), ask before `320` starts.
- [ ] 7.2 Delete the scratch clone and any temporary environment. Leave the downloaded GGUF in the shared cache unless the decision is to stop; then ask the owner whether to remove it. `openspec validate 310-dspark-streaming-evidence --strict`. No commit or push without a request.

## Findings during 1.2/1.3 (2026-10-28)

- The file's real name is `DeepSeek-V4.1-Flash-DSpark.gguf` (8 633 942 016 bytes, revision `57ddd58e`); the name in the proposal did not exist in the repo.
- At `cad7933` kernelpool's file does not bind: the loader wants `markov_head.embed.weight` and `markov_head.head.weight` for V4.1, the file has `markov_head.markov_w1.weight` and `markov_w2` (2 missing tensors). Mapping the names in the scratch clone made `ds41_draft_init` succeed.
- Three guards stand between #1073 and streaming: `g->streaming` in `ds41_draft_init`, the `--ssd-streaming is not compatible with --mtp-model yet` exit at engine open, and the Metal views. With the first two removed, the first verify fails: `Metal model range 2.04..3.13 GiB is not covered by mapped model views` (also 3.14..4.23, 4.24..5.62), then `V4.1 session batch failed at layer 1 (3 rows)`. Under streaming the support model's tensors are not mapped for the verify rows, so the gate is not a leftover: the PR has no streaming path for the drafter.
- Consequence: 2.x, 4.x and 5.x (anything needing a working drafter) wait for a port; 3.x uses D1's fallback.

- **Fallback D1 does not run either (2026-10-28).** A scratch build of main with `s->ds41_graph.streaming` removed from `ds41_sessions_batch_supported` and `session_concurrency_bench` opened with `--ssd-streaming` and the 82GB cache: 1 session decodes at 26.8 t/s, but 2, 3 and 4 sessions fail with the same three `not covered by mapped model views` ranges (2.04..3.13, 3.14..4.23, 4.24..5.62 GiB: layer 1's routed gate, up and down experts, 1.09 + 1.09 + 1.38 GiB) and `V4.1 session batch failed at layer 1`. The batched MoE has no streaming expert path, on main or in #1073. A drafter under streaming needs that path first (the prefill sweeps' layer buffers are the nearest existing mechanism); that is engine work, not a measurement, so 2.x, 3.x, 4.x and 5.x cannot run until it exists.
- **6.2, partial and not ticked.** A routing trace of 1024 decode tokens at frontier 2048 (`DS4_MOE_RECORD_SELECTED_IDS`, 82GB; the bench read 31.5 t/s) was replayed with the experts of k+1 consecutive tokens taken as one batch, 256 tokens of warm-up, 40 MoE layers. At 8078, 7648 and 7278 slots the results are identical, because 1024 tokens never evict: only first-touch misses are seen (2.1 experts per token). Miss layers per token fall as rows are batched, 2.03 (k=0), 1.96, 1.88, 1.80, 1.73, 1.68 (k=5), since first touches share a layer visit. That is a floor, not the steady state the `225` dump (3.91 miss layers per token, 2000+ tokens) describes; the cache-shrink question needs the longer trace.
