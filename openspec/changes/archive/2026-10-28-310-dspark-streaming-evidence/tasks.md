# Tasks

**Stopped 2026-10-28 at 3.4 (D7: under +10% on code, see "Margin verdict").** 2.2, 3.3, 4.x, 5.1 and 6.x were not run.

> Unblocked 2026-10-28: the V4.1 batch forced resident experts; with a `resident` flag and the vocabulary head per row, batch rows are bitwise under streaming. Resume at 2.1; see `design.md`, "Status".

## 1. Setup (scratchpad only)

- [x] 1.1 (2026-10-28, 1017 checkpoint, scratch clone `scratchpad/pr1073/ds4` at `cad7933`; cache line "effective 82.00 GiB = 7.12 GiB prefill headroom + 74.88 GiB dynamic cache (8078 experts)"; one cold 256-token run: prefill 6.48 t/s, generation 13.49 t/s, which includes the first token after a cold cache, so it is not a decode figure) Make a scratch clone of the upstream mirror at `pr/1073` (`cad7933`) in the scratchpad, without adding a worktree to the mirror, and build it. Verify: a plain greedy decode under `--ssd-streaming --ssd-streaming-cache-experts 82GB` at a 32768 context prints the admitted cache line and its tokens/s; record both.
- [x] 1.2 (2026-10-28, owner approved; the file is `DeepSeek-V4.1-Flash-DSpark.gguf`, 8 633 942 016 bytes, repo revision `57ddd58e`; header: `deepseek41-dspark`, `dspark.block_size` 5, target layers 37 38 39, markov rank 256, 128 experts top-3, hidden 5120, MXFP4 weights) With the owner approval, `hf download kernelpool/DeepSeek-V4.1-Flash-MXFP4-GGUF DeepSeek-V4.1-Flash-DSpark.gguf` into the shared cache. Verify with a stdlib GGUF header read: `dspark.block_size` 5, three stages, the target layers, and a hidden size matching the main model.
- [x] 1.3 (2026-10-28, FAILED under streaming, so D1 fallback applies to 3.x) Scratch patch: drop `g->streaming ||` from `ds41_draft_init`. Run `--dspark --mtp-model <file>` under streaming for 256 tokens. Verify there is no failure and the PR's acceptance counters print. On failure, record it and switch to D1's fallback for 3.x.

## 2. Output (D3)

- [x] 2.1 (2026-10-28: bitwise only in a reduced configuration, see "Root cause of the verify drift": per-row attention for verify rows plus `DS4_METAL_DISABLE_V41_ROWS_MMA=1`; 510 of 510 rows bitwise over 85 cycles) Row level: dump the logits of every verify row for 64 cycles, and the one-row logits at the same positions from a plain run. Verify bitwise. If it differs, find the configuration that is bitwise (MMA rows off first) and record which switches it needs.
- [ ] 2.2 (not run: stopped at 3.4) Token level: greedy 1024 tokens with and without `--dspark` on `tools/parity/sf-ds4-1flash.txt` and the four kinds (D2), in the configuration of 2.1. Verify identical tokens, or record the first differing position per prompt.

## 3. Verify cost (D4)

- [ ] 3.1 c(k) for k = 1..5 at 2048 and 8192, with forced length (cap k, confidence 0), split into GPU, waits and miss reads. Write `speed-bench/dspark-verify-curve.json` (D4). Verify that a plain run of the same binary gives t_decode within 2% of 1.1's, and that the file holds k = 0..5 at both frontiers.

- [x] 3.2 (2026-10-28, from 3.1's stage profiles rather than a separate run, at the owner's request to proceed fast: the exact profile gives the projections without MMA rows, the fast profile the batched attention core; see "Margin verdict") Attention bound (D9): exact MoE (`DS4_METAL_DISABLE_V41_ROWS_MMA=1`) with #1073's batched attention, oracle drafts, ~2K, k = 3 and 5, three runs each, plus one stage-profiled run at k = 3. Verify: c and the attention's per-row cost against 3.1's exact (+0.33) and fast (+0.17) rows.
- [ ] 3.3 (not run: the owner judged the routed-expert kernels already tuned (2026-10-28); the MoE row stays at the measured +0.30) MoE bound (D9): scratch micro-bench of the routed-expert kernels at 1, 2, 4 and 6 rows, distinct expert sets taken from a recorded verify cycle, no per-stage syncs. Verify: per-row ms and GB/s for each row count; the best per-row time is the MoE floor.
- [x] 3.4 (2026-10-28: under +10% on main, stop; see "Margin verdict") Margin verdict (D9): c with both bounds, projected onto main by D6, and the code gain at k = 1..5. Verify that the verdict quotes the band (+25% / +10..25% / under +10%).

## 4. Acceptance (D2)

- [ ] 4.1 (not run: stopped at 3.4) For each kind at confidence 0.4, 0.6, 0.8 and caps 2, 3, 5: acceptance per position, mean accepted length, mean drafted k. Verify that each cell has at least 200 cycles, or note why.
- [ ] 4.2 (not run: stopped at 3.4) The uncut cell per kind (confidence 0, cap 5) with `DS4_DSPARK_SPEC_LOG` captured to a file (D7b). Verify that every logged cycle has five confidences and an accepted length, and that at least 200 cycles per kind were logged.
- [ ] 4.3 (not run: stopped at 3.4) Offline replay (D7b), in a scratchpad script: #1073's rule over the grid, the expected-cost rule from `dspark-verify-curve.json`, and the oracle, per kind; plus the calibration table per position. Verify the replay against the run: for the cells measured in 4.1, the replayed mean accepted length is within 5% of the measured one.

## 5. End to end

- [ ] 5.1 (not run: stopped at 3.4) Plain against `--dspark` on one binary, ABBA, at least three quads per kind and frontier, with the default back-off and the best cap and confidence from 4.1. Report the medians and the pair-ratio CI. Verify that the prose arm shows whether back-off engaged (its skip counter).

## 6. Memory (D5)

- [ ] 6.1 (not run: stopped at 3.4) The `225` timeline with the drafter beside `82GB` at a 32768 context. Verify zero swapouts and no compressed engine pages, and record the minimum available memory.
- [ ] 6.2 (not run: stopped at 3.4) Replay the `225` decode dump with the cache shrunk by about 800 slots (and 430), and for unions of k+1 consecutive tokens. Verify that 8078 slots still reproduce 3.91 miss layers per token.

## 7. Decision

- [x] 7.1 (2026-10-28: `perf-record.md` section "DSpark verify cost under streaming" and a Rejected ideas row; `docs/upstream-prs.md` DSpark commits set to `history: verify`; no cap, confidence or draft-length rule to record on stop) Project onto main by D6, and apply D7.
  - Write the `perf-record.md` section: setup, the tables of 2-6, the projection and the verdict.
  - In `docs/upstream-prs.md`, set the DSpark commit lines of #1073 to the decision.
  - Record the drafter file (D8) and the default cap and confidence.
  - Record the draft-length rule `330` S4 starts from (D7b), with its replayed gain and the calibration verdict.

  Verify that every D7 condition is quoted with its number. If a condition needs the owner (output, prose tolerance, code at +10..25%), ask before `320` starts.
- [x] 7.2 (2026-10-28: scratch clones, patches, scripts and run outputs deleted; status lines in `320`-`350`; the diff check prints nothing; drafter GGUF left for the owner to decide) Clean close (D9). On stop: delete the scratch clones, patches, scripts and run outputs; do not write `dspark-verify-curve.json`; ask the owner about the drafter GGUF; add a status line to `320`, `330`, `340` and `350` naming 310's verdict and the reopen condition. On go: delete the scratch clones and keep the GGUF. Either way verify that `git diff --stat d4960f2 -- . ':!openspec' ':!speed-bench/perf-record.md' ':!docs/upstream-prs.md'` prints nothing, and `openspec validate 310-dspark-streaming-evidence --strict`. No commit or push without a request.

## Findings during 1.2/1.3 (2026-10-28)

- The file's real name is `DeepSeek-V4.1-Flash-DSpark.gguf` (8 633 942 016 bytes, revision `57ddd58e`); the name in the proposal did not exist in the repo.
- At `cad7933` kernelpool's file does not bind: the loader wants `markov_head.embed.weight` and `markov_head.head.weight` for V4.1, the file has `markov_head.markov_w1.weight` and `markov_w2` (2 missing tensors). Mapping the names in the scratch clone made `ds41_draft_init` succeed.
- Three guards stand between #1073 and streaming: `g->streaming` in `ds41_draft_init`, the `--ssd-streaming is not compatible with --mtp-model yet` exit at engine open, and the Metal views. With the first two removed, the first verify fails: `Metal model range 2.04..3.13 GiB is not covered by mapped model views` (also 3.14..4.23, 4.24..5.62), then `V4.1 session batch failed at layer 1 (3 rows)`. Under streaming the support model's tensors are not mapped for the verify rows, so the gate is not a leftover: the PR has no streaming path for the drafter.
- Consequence: 2.x, 4.x and 5.x (anything needing a working drafter) wait for a port; 3.x uses D1's fallback.

- **Fallback D1 does not run either (2026-10-28).** A scratch build of main with `s->ds41_graph.streaming` removed from `ds41_sessions_batch_supported` and `session_concurrency_bench` opened with `--ssd-streaming` and the 82GB cache: 1 session decodes at 26.8 t/s, but 2, 3 and 4 sessions fail with the same three `not covered by mapped model views` ranges (2.04..3.13, 3.14..4.23, 4.24..5.62 GiB: layer 1's routed gate, up and down experts, 1.09 + 1.09 + 1.38 GiB) and `V4.1 session batch failed at layer 1`. The batched MoE has no streaming expert path, on main or in #1073. A drafter under streaming needs that path first (the prefill sweeps' layer buffers are the nearest existing mechanism); that is engine work, not a measurement, so 2.x, 3.x, 4.x and 5.x cannot run until it exists.
- **6.2, partial and not ticked.** A routing trace of 1024 decode tokens at frontier 2048 (`DS4_MOE_RECORD_SELECTED_IDS`, 82GB; the bench read 31.5 t/s) was replayed with the experts of k+1 consecutive tokens taken as one batch, 256 tokens of warm-up, 40 MoE layers. At 8078, 7648 and 7278 slots the results are identical, because 1024 tokens never evict: only first-touch misses are seen (2.1 experts per token). Miss layers per token fall as rows are batched, 2.03 (k=0), 1.96, 1.88, 1.80, 1.73, 1.68 (k=5), since first touches share a layer visit. That is a floor, not the steady state the `225` dump (3.91 miss layers per token, 2000+ tokens) describes; the cache-shrink question needs the longer trace.

## Findings after the unblock (2026-10-28, #1073 `cad7933` + scratch patch, 1017 checkpoint, streaming 82GB, greedy, one C-code prompt)

- **Verify runs under streaming.** `--dspark --mtp-model DeepSeek-V4.1-Flash-DSpark.gguf`: 131 verify cycles in 512 tokens, no mapping error. 1.3's failure is resolved by the `resident` flag.
- **The drafter does not work with kernelpool's file at `cad7933`.** 124 of 131 cycles accept 0 of 5 drafts, 5 accept 1. The printed confidences are about 1000 (sigmoid saturates, so k is always 5) and the drafts repeat tokens. Binding `markov_w1/w2` the other way round accepts nothing either. Cause not found; any acceptance figure from this file is meaningless.
- **2.1, verify rows against one-row decode (scratch dump `DS4_SCRATCH_LOGIT_DUMP`):** rows whose input token matches the plain run, before the token streams diverge (position 219): 135 rows, **0 bitwise**, max_abs 4.06, already 1.81 on the first row of the first cycle (position 45). Top-1 matched on all 135. Default and `--dspark-strict` produce the same text, which differs from the plain run at character 738.
- **D3's switches do not restore it:** `DS4_METAL_DISABLE_V41_ROWS_MMA=1` alone, and with every row/batch variant off as well (`VERIFY_TILED_INDEX`, `BATCH_TOPK`, `TOPK_*`, `BATCH_INDEX*`, `BATCH_COMPRESS`, `ROUTER_BATCH`, `ROUTER_MM`, `MOE_DEDUP`, `BATCH_HC`, `BATCH_CORE`, `MXFP4_TINY_BATCH`): 64 rows, 0 bitwise, max_abs 3.76 (1.02 on the first row), and the text diverges earlier (character 275).
- **Contrast with main:** main's session batch (rows of different sessions) is bitwise with the head per row. The #1073 verify (consecutive rows of one session) is off by up to 4 logits even on row 0, so the difference is structural (within-block attention, compression or indexer state, or the rejected rows' writes), not reduction order. Not yet localized.
- The plain run is repeatable (two runs, identical text).
- Plain speed in this tree: generation 19.3 t/s at 512 tokens; with the broken drafter and back-off, `--dspark` 11.8 t/s (strict 9.1). Not decision figures.
- **Oracle drafts (scratch `DS4_SCRATCH_ORACLE`: the drafts are the plain run's own next tokens):** 60 cycles accept 5 of 5 until the streams split at position 251; the top-1 of every verify row matches the plain run up to there. Logits are still not bitwise: 206 rows, 0 bitwise, median max_abs 0.63, p90 1.43, max 2.93, and row 0 of the first cycle (position 45) is off by 1.81, as with the broken drafter. Default and `--dspark-strict` give the same text, split from the plain run at character 866.
- **Localized to the verify batch itself.** `--dspark` with zero drafts (every cycle k = 0: prefill with capture, propose, one-row decode) is bitwise with the plain run, 128 of 128 positions. So prefill and capture are exact. The first verify's row 0, with the same state and the same input token as one-row decode, differs by 1.81, and the one-row steps after verify commits inherit the drift (39 of 39 differ in the broken-drafter run). Main's session batch, whose rows belong to different sessions, is bitwise. What differs is a batch of consecutive rows of one session: in-block attention, compression or indexer over the block, or the verify's own logits path (`hc_weighted_sum_split_tensor`, `ds41_norm_batch`, exact Q8_0 rows head). Not localized further.
- **Memory, oracle runs (#1073 tree, no lock-ahead, drafter mapped beside 82GB):** swap used 0.06 -> 1.31 MB, swapouts 4 -> 84 pages, compressed pages +2.8 GiB, free memory down to about 12 GiB. Small, but not D5's "zero swapouts"; to be repeated on a tree with `270`'s lock-ahead before any verdict.

## Root cause of the verify drift (2026-10-28)

Method: scratch dumps of the HC residual entering every layer, and of layer 0's intermediate tensors, for row 0 of the first verify (position 45) against one-row decode at the same position; oracle drafts capped at k = 1..5; a deliberately wrong draft to test causality.

- **Row 0 is causal.** With k = 1 and k = 2, a wrong draft token leaves row 0 bitwise unchanged in all 40 layers. There is no leak from future rows, including through the compressed groups the block completes.
- **Cause 1, the batched attention.** `ds41_graph_step_batch` with `prefill_only` (every verify) attends the block with `ds41_attention_batch`, the prefill kernel. A scratch switch that sends verify rows through the per-row `ds41_attention` (as the session batch does) makes row 0 bitwise in all 40 layers at k = 1.
- **Cause 2, the MMA rows.** From 3 rows (k >= 2) the Q8_0 rows matmul takes `kernel_mul_mv_q8_0_*_mma_rows` (`n_rows >= 3` when `in_dim < 8192`); in layer 0 the `attn_kv` projection then differs from decode in 3 of 512 values by one BF16 ulp, and the drift grows from there. `DS4_METAL_DISABLE_V41_ROWS_MMA=1` removes it: with per-row attention, row 0 at k = 5 is bitwise in all 40 layers. These are the kernels `70` dropped as `drop: output` (`262b4a6`, `a6b50ff`).
- **Both off, full check.** Oracle drafts, 512 tokens: 85 cycles, all accept 5 of 5; 510 of 510 verify rows bitwise with one-row decode (max_abs 0); greedy text identical to the plain run.
- **#1073's session batch** (rows of different sessions, streaming, head per row) passes `test_metal_session_batch` bitwise: the drift is specific to consecutive rows of one session.
- **Indicative speed, not a decision figure** (one cold run each, scratch dumps on): with both fixes and perfect drafts (6 tokens a cycle), generation 24.1 t/s against 19.0-19.3 t/s plain on the same tree, about +25%. A cycle of 6 rows costs about 4.7 plain tokens, so c is roughly 0.7 per extra row in this configuration (per-row attention, no MMA rows), well above D7's c(3) <= 0.3. 3.1 measures it properly.

## 3.1 measured, not ticked (2026-10-28)

Scratch #1073 tree with the fixes above, 1017 checkpoint, streaming 82GB, ctx 32768, greedy, `promessi_sposi.txt` prompts of 2074 and 8417 tokens, oracle drafts forced to k = 0..5 (`DS4_SCRATCH_ORACLE_K`, confidence 100, `DS4_DSPARK_DISABLE_ADAPTIVE_DRAFTING=1`), one run per cell. Times are medians of per-step/per-cycle timestamps after a warm-up (128 tokens at 2K, 32 at 8K). "exact" = per-row attention + `DS4_METAL_DISABLE_V41_ROWS_MMA=1` (bitwise); "fast" = #1073's default (batched attention, MMA rows; not bitwise). Scratch data: `scratchpad/c31/curve.json`, `curve-w32.json`.

| frontier | config | t_decode | t_draft (D) | c(1) | c(2) | c(3) | c(4) | c(5) |
|---|---|---|---|---|---|---|---|---|
| 2074 | exact | 42.3 ms | 14.8 ms (0.35) | 0.63 | 0.59 | 0.58 | 0.58 | 0.58 |
| 2074 | fast | | | 0.41 | - | 0.32 | - | 0.34 |
| 8417 | exact | 46.5 ms | 17.1 ms (0.37) | 0.66 | 0.54 | 0.53 | 0.53 | 0.51 |
| 8417 | fast | | | 0.44 | - | 0.31 | - | 0.29 |

- Speedup if every draft were accepted (exact, 2K): k=1 1.01x, k=3 1.29x, k=5 1.42x. With the code profile of the design (0.82, 0.67, 0.54, 0.45, 0.37): exact 0.91-0.99x at 2K and 0.90-1.02x at 8K; fast 1.27-1.31x at 2K and 1.31-1.37x at 8K.
- D6 projection onto main (34 ms a token at 2048): exact c about 0.72 and D about 0.44, code 0.84-0.87x; fast c about 0.41, code at best 1.14x (k=3). D7 needs +25% on code and c(3) <= 0.3: neither configuration passes, and the fast one also fails output.
- Missing against the task text: the split into GPU, waits and miss reads; the 2% check against 1.1 (1.1 recorded a cold whole-run rate, not a steady decode time); several runs per cell. The 8K exact cells have n = 23-42 cycles.
- **New at 8K:** in the #1073 tree `--dspark` changes the output even with k = 0 (no verify), so the long-prompt prefill differs between the two modes there (the 2K prompt was bitwise). Not investigated; main's decoder-suffix fix (`401`) is a candidate. The 8K exact cycles therefore ran with rejected drafts.
- Memory over the batch: swapouts 220 -> 384 pages, swap used 3.4 -> 6.0 MB, compressed pages +4.6 GiB.

### Complete batch, three runs per cell (2026-10-28 evening)

Same tree and switches, translation prompts (`promessi_sposi.txt` excerpt behind an "translate into English" instruction) of 2069 and 8408 tokens, so the oracle drafts come from `--dspark` k = 0 runs and every exact cycle accepts all k drafts. The "fast" runs get the same oracle drafts, but their output leaves the exact text early (not bitwise), so the drafts stop matching: 2K about 0.02 accepted per cycle; 8K 0.47 at k = 3, 1.55 at k = 5. Warm-up 128 tokens, medians per run, then the median over runs r1-r3 with the range. Scratch data: `scratchpad/c31b/curve.json`, `analyze2.py`. k = 4 was not repeated (first batch only).

| frontier | config | t_decode | D | c(1) | c(2) | c(3) | c(5) |
|---|---|---|---|---|---|---|---|
| 2069 | exact | 43.4 ms | 13.8 ms (0.32) | 0.65 (0.57-0.65) | 0.64 (0.53-1.02) | 0.58 (0.53-0.74) | 0.58 (0.53-0.69) |
| 2069 | fast | | | 0.39 (0.29-0.73) | - | 0.32 (0.26-0.50) | 0.39 (0.32-0.40) |
| 8408 | exact | 47.9 ms | 15.0 ms (0.31) | 0.66 (0.63-0.68) | 0.63 (0.56-0.63) | 0.60 (0.57-0.60) | 0.58 (0.57-0.58) |
| 8408 | fast | | | 0.35 (0.33-0.37) | - | 0.31 (0.31-0.33) | 0.28 (0.28-0.30) |

- **Split per token / per extra verify row** (r3; pread is summed over reader threads, so it is work, not wall):

  | | wall | GPU | wall not on GPU | misses | pread |
  |---|---|---|---|---|---|
  | plain token, 2K | 43.3 ms | 29.1 ms | 14.2 ms | 5.0 | 2.5 ms |
  | extra row, exact k=5, 2K | +25.2 ms | +18.0 ms | +7.2 ms | +5.4 | +4.4 ms |
  | extra row, exact k=5, 8K | +26.6 ms | +18.3 ms | +8.3 ms | +5.2 | +5.4 ms |
  | extra row, fast k=3, 2K | +13.6 ms | +8.8 ms | +4.8 ms | +2.7 | +2.1 ms |

  An exact extra row costs about 0.6 of a token, and its GPU share (71%) is the same as a plain token's (67%). Each row adds about 5 misses and 4-5 ms of reader work, against 18 ms of GPU. **The cost is compute, not the SSD.**
- **Stage profile** (scratch copy `pr1073-prof`, command buffers synced at every stage, so absolute times are inflated; ms per layer, 2K):

  | stage | 1 row (plain) | exact 4 rows | exact 6 rows | fast 4 rows |
  |---|---|---|---|---|
  | pre-attention | 0.19 | 0.20 | 0.23 | 0.20 |
  | attention (proj + core + out) | 0.54 | 1.53 | 2.10 | 1.04 |
  | FFN norm | 0.18 | 0.20 | 0.21 | 0.18 |
  | MoE (routed + shared) | 0.70 | 1.61 | 2.16 | 1.31 |
  | expand | 0.17 | 0.17 | 0.17 | 0.20 |

  Per extra row, exact: attention +0.31-0.33, MoE +0.29-0.30, everything else about 0. Fast: attention +0.17, MoE +0.20. Batching the attention halves its per-row cost; the MoE gap is partly the Q8_0 MMA rows and partly a confound: the fast runs' rejected drafts repeat positions, so they miss half as often (+2.7 against +5.4 a row). Fast c is therefore optimistic.
- **Projection.** With the design's code profile and D = 0.32 on this tree: exact 0.95x (k=1), 0.99x (k=2), 0.97x (k=3), 0.89x (k=5); fast 1.11x, 1.26x, 1.31x, 1.30x. Onto main (34 ms a token, so D and c × 1.28): exact about 0.85x at every k, fast at best 1.15x (k=3). D7: exact is under +10% (stop); fast is in the +10..25% band but fails output (stop), and c(3) ≤ 0.3 fails for both.
- **Not ticked** for two deviations the owner may accept: k = 4 has one run, and the 2% check against 1.1 cannot be run as written (1.1 recorded a cold whole-run rate). The same binary's plain decode varied 43.3-44.8 ms over three runs (3.4%). `speed-bench/dspark-verify-curve.json` is not written yet: it waits for the decision.
- Memory over the four blocks: swap used 6.0 -> 17.4 MB, swapouts 384 -> 1116 pages (the #1073 tree has no lock-ahead); small, but not the zero D5 asks for.

## Margin verdict (3.2-3.4, 2026-10-28)

Per extra verify row and layer, from the synced 2K profiles (exact k = 3 against plain): attention +0.33, MoE +0.30, the other stages +0.01; 0.64 in all.

- **Attention bound.** An exact batched attention can at best cost what #1073's batched core costs, with the projections still without MMA rows: 0.35 (exact projections) + 0.74 (fast core and output) = 1.09 ms for 4 rows against 0.54 for one, so +0.18 a row instead of +0.33.
- **MoE.** Kept at the measured +0.30 (3.3 not run). The rows of one user pick mostly different experts, and the `mul_mv_addr` kernels read one (row, expert) pair at a time, so there is nothing to share.
- **c with the bound:** 0.18 + 0.30 + 0.01 = 0.49 against 0.64, so c about 0.46 on #1073's tree and about 0.59 on main (D6, x1.28), with D about 0.41 on main.
- **Code gain on main** (design's profile): k = 1 0.91x, k = 2 0.96x, k = 3 0.96x, k = 4 0.93x, k = 5 0.89x. On #1073's tree at best 1.12x (k = 3).
- **Even with a MoE floor** of +0.11 a row (the kernels at full bandwidth, which the owner does not expect): c about 0.36 on main and 1.22x at k = 3, still under D7's +25% and above c(3) <= 0.3.

**Verdict: stop** (D7, under +10%). Reopen only with a verify row that costs at most 0.3 of a decode token on main.
