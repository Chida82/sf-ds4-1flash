# Tasks

## 1. Branch and base tree

- [x] 1.1 From a clean `main` (`b044217`), `git switch -c perf/50-ssd-miss-overlap`; `git worktree add --detach ../sf-ds4-1flash-base main`, its `deepseek-v4.1-flash.gguf` symlink pointed at the same blob as the checkout's, `make -j8` in it. Verify `git status --short --branch` shows only this change's `openspec/` files and the base tree's bench exists.

## 2. S0: diagnosis

- [x] 2.1 On `main`, the bench with `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1 --cache-stats` (harness streaming flags): `--frontiers 2048 -n 16`, `--frontiers 2048 -n 256`, `--frontiers 8192 -n 256`, `--frontiers 5000 -n 16`, one process at a time. Verify every run exits 0 and each stderr has the `streaming pread pool` line.
- [x] 2.2 Compute per decode token (2048: 256-token run minus 16-token run) and per tail step (cold-5000): `sync`, pread (pool wall), buffer preparation (`load_prepare_avg × load_calls`), misses; add them as a second table ("after `40`") in the Read path section of `speed-bench/perf-record.md`. Evaluate design D1's S2 gate and write the verdict (open or closed, with the numbers) under the table.

## 3. S1: early load

- [x] 3.1 Restore `ds4_gpu_glm_stream_selected_prefetch_set` and `ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor` verbatim from upstream `0aaea5a` `ds4_metal.m` into the child next to the existing consumer, and the declaration into `ds4_gpu.h`. Verify `make -j8` has no warnings and `nm ds4_metal.o | grep begin_selected_load_tensor` shows the symbol.
- [x] 3.2 Add `a3043bb`'s hook in `ds4.c` `ds41_moe_partial`, after `router_select` and before the shared expert, without the `imatrix` term. Verify `make -j8` has no warnings, `make test` names its tests, `make test-metal-ssd-experts` passes.
- [x] 3.3 Correctness on the model: one parity prompt, `--ssd-streaming --temp 0 --nothink -n 64`, on the S1 tree, on the S1 tree with `DS4_METAL_DISABLE_GLM_STREAMING_EXPERT_EARLY_LOAD=1`, and on the base tree; all three token streams identical. One bench run with the timing summary shows the early load in use (the consumer takes the ids: `sync` recorded by the producer, `selected_calls` unchanged). No `--quality` run in this task.
- [x] 3.4 A/B S1 against the base (design D3), a second invocation pooled unless the first is a drop (design D2). Verify correctness PASS, equal cache counters, and record the decision with both rows.
- [x] 3.5 Kept: a "Names that lie" row in `AGENTS.md` (the `glm_stream_*` early-load producer and consumer serve V4.1 decode) and the switch among the knobs; short review (the producer clears `active` on every path, the consumer's field match, the hook's guard keeps TP and `--quality` off). Dropped: revert 3.1-3.2, delete the consumer, its struct and its call, with an `sf-ablate(glm)` marker at the call site; verify `make -j8` no warnings and `make test` names its tests.

## 4. S2: #849 (only if 2.2 opened it)

- [x] 4.1 (Closed by 2.2: 0.46 x 2.23 ms = 1.03 ms against 1.37 ms.) If 2.2 closed S2, mark this task with the numbers and go to 5. Otherwise port `60051d4` (F32 router registration, no hash-router or GLM hunks, staging buffers, retain mark), `make -j8` no warnings, `make test`, and A/B against the S1 tree with at least +1.5% on `decode 8192`; cache counters reported, not gated (the retain mark changes them by design); bitwise required.

## 5. Close

- [x] 5.1 Final pass over the touched regions against `AGENT.md`; delete what the outcome made dead. Verify `make -j8` no warnings, `make test` names its tests, `make test-metal-ssd-experts` passes.
- [x] 5.2 (Not run: S1 was reverted, and the tree differs from `main` only by the deleted unreachable consumer, so the row would repeat `40`'s; recorded in `perf-record.md`.) Record row: `git worktree add --detach ../sf-ds4-1flash-start 7dea5e3` (gguf symlink, `make -j8`), the final tree against it with `--kinds decode,cold-2500,cold-5000 --guards guard-decode --bitwise`; paste the row into segment 1 of `speed-bench/perf-record.md`. Verify its `decode 8192` gain is at least the `40` row's minus the A/A noise (±1.6%).
- [x] 5.3 Docs and registry per design D5. Verify `grep -n "a3043bb\|60051d4" docs/upstream-prs.md` shows the new verdicts and nothing else in the registry changed.
- [x] 5.4 Closing parity from the StarForge checkout: `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`. Verify `PARITY OK (10 prompts)`.
- [x] 5.5 Scope: `git diff main --stat` lists only `ds4_metal.m`, `ds4_gpu.h`, `ds4.c`, `AGENTS.md`, `speed-bench/perf-record.md`, `docs/upstream-prs.md` and this change's `openspec/` files (plus #849's files if S2 ran); `git worktree list` shows only the checkout; `openspec validate 50-ssd-miss-overlap --strict` passes.
