# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request. Model runs use `--ssd-streaming` and `82GB` (speed), or the largest admitted cache (quality).

## 1. Go/no-go (no code)

- [ ] 1.1 On today's binary, run `cold-2500`, `cold-5000` and `cold-10000` once each, under `DS4_METAL_V41_STAGE_PROFILE=1 DS4_METAL_GRAPH_PREFILL_PROFILE=1`. Confirm the sweep shapes in the design's Context table, then compute D1's ceiling per shape and for the typical mix. Verify the per-layer sums against `perf-record.md`'s decomposition (2048-row sweep stages 9.1-10.2 s; `cold-10000` suffix about 4 s), and record the table in `perf-record.md`.
- [ ] 1.2 Stop rule (D1). If the ceiling is under the harness's resolution on all three shapes, record the verdict and stop, and the change is archived as history. Otherwise report the ceiling to the owner before 2.x.

## 2. The cut (S1)

- [ ] 2.1 Harness tool step (D7, S0): `ab_bench.py --approximate`. Verify an A/A run with and without it gives the same rows, and that without it a token difference still fails.
- [ ] 2.2 Segment start in `ds41_attention_batch` (D3). Add a model-less test: a synthetic segment against a truncating CPU reference, plus a sentinel-filled ring that no attention reads. Verify `make test` names it, and that the default path computes `previous` exactly as before.
- [ ] 2.3 The flag in the engine options, CLI, server and bench, and the cut in `ds41_graph_prefill_sweep` (D2, D4). Pick the smaller of D4's two ways for sweeps that are not wide, and align the `selected_comp` offset. Verify that a 10000-token and a 2000-token prompt generate with the flag, and that the prefill profile shows 128 decoder rows per sweep.
- [ ] 2.4 Refusals (D6): persistence for a flagged session, the server's disk cache, and the flag with steering. Verify each spec scenario by running it.
- [ ] 2.5 Flag off (D5): `make test`, the model-backed prefill tests (`tests/test_deepseek41_graph MODEL --decoder-suffix PROMPT_FILE`, `make test-deepseek41-prefill-replica REPLICA=<path>`), `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout, and the harness without the flag, `--bitwise`, against the segment's start commit. Verify that all of them pass bitwise and that no metric is below zero.
- [ ] 2.6 Flag on (D8): the harness with `--b-bench-arg --approx-decoder-prefill --approximate` on the cold kinds, with `decode` as a guard. Verify the keep rule on time to first token and that decode is not below zero; append the rows to `perf-record.md`.

## 3. Optional S2

- [ ] 3.1 Only if S1 is kept: skip decoder layers in sweeps followed by another batched sweep (D2), and measure on `cold-10000` with the flag against S1. Verify the keep rule, and that no token-major tail follows a skipped sweep.

## 4. Quality (D9)

- [ ] 4.1 Flag on against off: first-token agreement and first divergence on the parity prompts (512 tokens), `./sf-ds4-1flash-eval --suite core`, the long-story recall test and the 10K retrieval prompt, and first-token KL and top-1 agreement on 20 prompts. Verify each number is recorded with its run id, and do not read completion text beyond what the scorers report.

## 5. Docs and close

- [ ] 5.1 Record the exception:
  - an `AGENTS.md` Identity row: the flag, approximate, off by default, refused with steering and persistence, and its measured gain and quality cost;
  - a `README.md` section for the flag;
  - the `prefill-schedule` spec through this delta;
  - one sentence in `openspec/config.yaml`'s context, after "no prefill schedule or kernel that alters bits": the opt-in `--approx-decoder-prefill` is the one approved exception. It is added when the flag lands, so later proposals are not judged against a rule that ignores it.

  Verify that no doc line says or suggests the flag is exact.
- [ ] 5.2 Reviews per the config (short after S1, final pass over the touched region). Then `make test`, parity without the flag, and `openspec validate 530-v41-compact-decoder-optin --strict`.
