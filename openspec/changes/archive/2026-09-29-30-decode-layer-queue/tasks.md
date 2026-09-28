# Tasks

## 1. Branch and start row

- [x] 1.1 From a clean `main` (`7dea5e3`), `git switch -c perf/30-decode-layer-queue`; verify `git status --short --branch` shows the new branch with no changes.
- [x] 1.2 Start row (design D4): `git worktree add ../sf-ds4-1flash-start 7dea5e3`, then with nothing else resident `python3 speed-bench/ab_bench.py --a ../sf-ds4-1flash-start --b ../sf-ds4-1flash-start --kinds decode,cold-2500,cold-5000 --guards guard-decode`. Verify exit 0, every pair kept, and paste the printed row as the first row of segment 1 in `speed-bench/perf-record.md` with the step cell `start (A/A)`.

## 2. S0: test and bench flag

- [x] 2.1 Port `check_stream_decode_queue` from #1034 `9b50495` into `tests/test_deepseek41_graph.c` as the `--stream-decode-queue-parity` mode: control with `DS4_METAL_DISABLE_V41_DECODE_QUEUE=1`, candidate with it unset, `ssd_streaming_cache_experts = 512`, 120 synced tokens, 24 decoded, logits, `history` and `ds41_state_spans` compared bitwise; usage line updated. Verify `make tests/test_deepseek41_graph` builds without warnings and `./tests/test_deepseek41_graph <gguf> --stream-decode-queue-parity` prints its PASS line (trivially, both sides drained).
- [x] 2.2 Add `--ssd-streaming` and `--ssd-streaming-cache-experts N|NGB` to `speed-bench/metal_decode_schedule_bench.c` (parsed with `ds4_parse_streaming_cache_experts_arg`, passed to `ds4_engine_options`), and the two lines to its usage. Verify `make metal-decode-schedule-bench` builds and `./speed-bench/metal_decode_schedule_bench --help | grep -c ssd-streaming` prints 2.
- [x] 2.3 Short review of S0 (no engine change, the test frees what it opens on every path, the bench flag reaches the engine options); `make -j8` no warnings; `make test` names its tests as run.

## 3. S1: the queue

- [x] 3.1 In `ds41_graph_step`: `queue_layers` becomes `!layer_resident && !getenv(g->tp_world == 2 ? "DS4_METAL_DISABLE_V41_TP_DECODE_QUEUE" : "DS4_METAL_DISABLE_V41_DECODE_QUEUE")`; after the drain block, `if (ok && !drain && queue_layers && g->tp_world == 1 && !getenv("DS4_METAL_DISABLE_V41_DECODE_FLUSH") && !ds4_gpu_flush_commands()) ok = false;` with the PR's comments trimmed to what holds here. Verify `make -j8` prints no warnings and `git diff --stat ds4.c` is under 25 lines.
- [x] 3.2 Model-backed checks: `./tests/test_deepseek41_graph <gguf> --stream-decode-queue-parity` PASS (now a real comparison); one parity prompt with `--ssd-streaming --quality --temp 0 --nothink -n 64` decodes 64 tokens with exit 0 (the `layer_resident` fix), and its tokens equal the same command on the start worktree; `DS4_METAL_DISABLE_V41_DECODE_QUEUE=1` and `_FLUSH=1` each decode the same tokens.
- [x] 3.3 A/B S1 against the start: `python3 speed-bench/ab_bench.py --a ../sf-ds4-1flash-start --b . --kinds decode,cold-2500,cold-5000 --guards guard-decode --bitwise`. Verify correctness PASS (tokens; bitwise), no pair dropped for cache state, and record the gains and intervals of `decode 8192`, `decode 2048`, `ttft 2500`, `ttft 5000` and the guard. If `decode 8192`'s interval straddles zero, run a second invocation and pool with `ab_pool.py decode --metric "decode 8192" <dir1> <dir2>`. Keep S1 only if the pooled interval lies above zero and no other metric's lies wholly below.
- [x] 3.4 Same-engine cross-check: `./speed-bench/metal_decode_schedule_bench -m <gguf> --ssd-streaming --ssd-streaming-cache-experts 82GB --candidate-env DS4_METAL_DISABLE_V41_DECODE_QUEUE --include-selection --tokens 256`. Verify it reports every logit row bit-identical and prints the control/candidate ratio; note it next to the harness's figure.
- [x] 3.5 Short review of S1 (switch names, `tp_world == 1` on the flush, the drains unchanged, no per-layer `getenv`); `make test` names its tests.

## 4. S2: the variant

- [x] 4.1 `git worktree add ../sf-ds4-1flash-s1 HEAD` after committing S1 on the branch (a local commit on the change branch, squashed at landing). Apply `2a281b08` minus its `ds41_graph_step_batch` hunk and `29ce2717`: `ds41_decode_flush_layers()` (default 2, `DS4_METAL_V41_DECODE_FLUSH_LAYERS`), `engram_rows_b` in the tensor list, both tables written before `ds4_gpu_begin_commands`, `ds41_graph_before_attention` reading `engram_rows_b` for the second table, the layer-13 drain kept only for `tp_world == 2`, the sweep alias. `DS4_METAL_DISABLE_V41_DECODE_FLUSH` goes (period 0 replaces it). Verify `make -j8` no warnings; the S0 test PASS; the `--quality` prompt of 3.2 unchanged; a 2500-token cold prompt's tokens equal the start worktree's (the sweep alias).
- [x] 4.2 A/B S2 against S1: `--a ../sf-ds4-1flash-s1 --b . --kinds decode,cold-2500,cold-5000 --guards guard-decode --bitwise`; pool a second invocation if needed. Decide by design D1: S2 stays only if `decode 8192`'s pooled interval lies above zero and nothing lies wholly below; otherwise `git revert` S2's commit and record the numbers in the registry lines of `2a281b0` and `29ce2717`.
- [x] 4.3 Short review of the surviving step; remove the S1 worktree (`git worktree remove --force ../sf-ds4-1flash-s1`).

## 5. Close

- [x] 5.1 Final pass over `ds41_graph_step` against `AGENT.md` and the surrounding idiom, deleting anything the surviving step made dead (an unused switch, an unused static). Verify `make -j8` no warnings, `make test` names its tests, and the S0 test still passes.
- [x] 5.2 Record row: the final tree against the start worktree, `--kinds decode,cold-2500,cold-5000 --guards guard-decode --bitwise`; paste the row into `speed-bench/perf-record.md`. Verify the row's `decode 8192` gain agrees with the step gains combined.
- [x] 5.3 Docs: the schedule bench section of `speed-bench/README.md` (the two flags, the rollback command); the switches next to the other `DS4_METAL_DISABLE_V41_*` names in the doc that lists them (`grep -l DISABLE_V41 docs/*.md`); update `docs/upstream-prs.md` lines for #1041 `bd6f912`, #1034 `9b50495`, #1073 `2a281b0` and `29ce2717` with the measured outcome, and touch nothing else in the registry. Verify `grep -n DECODE_QUEUE docs/*.md speed-bench/README.md` finds each name once where it is documented.
- [x] 5.4 Closing parity: `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout. Verify `PARITY OK (10 prompts)`.
- [x] 5.5 Scope: `git diff main --stat` lists only `ds4.c`, `tests/test_deepseek41_graph.c`, `speed-bench/metal_decode_schedule_bench.c`, `speed-bench/README.md`, `speed-bench/perf-record.md`, the switch doc, `docs/upstream-prs.md` and this change's `openspec/` files; `git worktree list` shows only the checkout (the start worktree removed); `openspec validate 30-decode-layer-queue --strict` passes.
