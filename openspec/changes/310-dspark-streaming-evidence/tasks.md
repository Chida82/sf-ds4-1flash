# Tasks

## 1. Setup (scratchpad only)

- [ ] 1.1 Make a scratch clone of the upstream mirror at `pr/1073` (`cad7933`) in the scratchpad, without adding a worktree to the mirror, and build it. Verify: a plain greedy decode under `--ssd-streaming --ssd-streaming-cache-experts 82GB` at a 32768 context prints the admitted cache line and its tokens/s; record both.
- [ ] 1.2 With the owner's approval, `hf download kernelpool/DeepSeek-V4.1-Flash-MXFP4-GGUF DeepSeek-V4.1-Flash-DSpark-MXFP4.gguf` into the shared cache. Verify with a stdlib GGUF header read: `dspark.block_size` 5, three stages, the target layers, and a hidden size matching the main model.
- [ ] 1.3 Scratch patch: drop `g->streaming ||` from `ds41_draft_init`. Run `--dspark --mtp-model <file>` under streaming for 256 tokens. Verify there is no failure and the PR's acceptance counters print. On failure, record it and switch to D1's fallback for 3.x.

## 2. Output (D3)

- [ ] 2.1 Row level: dump the logits of every verify row for 64 cycles, and the one-row logits at the same positions from a plain run. Verify bitwise. If it differs, find the configuration that is bitwise (MMA rows off first) and record which switches it needs.
- [ ] 2.2 Token level: greedy 1024 tokens with and without `--dspark` on `tools/parity/sf-ds4-1flash.txt` and the four kinds (D2), in the configuration of 2.1. Verify identical tokens, or record the first differing position per prompt.

## 3. Verify cost (D4)

- [ ] 3.1 c(k) for k = 1..5 at 2048 and 8192, with forced length (cap k, confidence 0), split into GPU, waits and miss reads. Verify that a plain run of the same binary gives t_decode within 2% of 1.1's.

## 4. Acceptance (D2)

- [ ] 4.1 For each kind at confidence 0.4, 0.6, 0.8 and caps 2, 3, 5: acceptance per position, mean accepted length, mean drafted k. Verify that each cell has at least 200 cycles, or note why.

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

  Verify that every D7 condition is quoted with its number. If a condition needs the owner (output, prose tolerance, code at +10..25%), ask before `320` starts.
- [ ] 7.2 Delete the scratch clone and any temporary environment. Leave the downloaded GGUF in the shared cache unless the decision is to stop; then ask the owner whether to remove it. `openspec validate 310-dspark-streaming-evidence --strict`. No commit or push without a request.
