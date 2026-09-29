# Tasks

## 1. Branch and base tree

- [x] 1.1 From a clean `main` (`5410123`), `git switch -c perf/40-ssd-expert-reads`; `git worktree add --detach ../sf-ds4-1flash-base main` and point its `deepseek-v4.1-flash.gguf` symlink at the same blob as the checkout's; `make -j8` in it. Verify `git status --short --branch` shows the branch with only this change's `openspec/` files, and the base tree's bench exists.

## 2. S0: tool

- [x] 2.1 Port `a1afb82` (pool dispatch stats in the timing summary). Verify `make -j8` has no warnings and `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1 ./sf-ds4-1flash-bench --ssd-streaming --ssd-streaming-cache-experts 82GB --ctx-alloc 32768 --prompt-file speed-bench/promessi_sposi.txt --frontiers 2048 --gen-tokens 16 --cache-stats` prints one `streaming pread pool dispatches=` line per memory report.
- [x] 2.2 Add `--b-env KEY=VALUE` to `speed-bench/ab_bench.py` (repeatable, B only, on top of `--env`; the summary's `env` line shows both sides; no record row when set) and one test in `tests/test_ab_bench.py` asserting B's environment carries the pair and A's does not. Verify `python3 tests/test_ab_bench.py` passes every test, including the new one.
- [x] 2.3 A/B S0 against the base: `python3 speed-bench/ab_bench.py --a ../sf-ds4-1flash-base --b . --kinds decode,append,cold-5000 --guards guard-decode --bitwise --budget 2700`. Verify exit 0, correctness PASS (tokens; bitwise), and no metric's CI wholly below zero.
- [x] 2.4 Diagnosis: the bench on the S0 tree for `decode` (frontiers 2048 and 8192) and `cold-5000` with `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1 --cache-stats`, one run each. Record `qd_avg`, `pool_gbps`, `task_gbps`, `wall_avg` and `tasks_avg` per frontier in a new "Read path" subsection of `speed-bench/perf-record.md`, with the verdict latency- or bandwidth-bound (design, Risks: a pool already at the SSD's bandwidth cuts the split sweep to split 4).
- [x] 2.5 Short review of S0 (stats only accumulate under the pool mutex; `--b-env` never reaches A; no record row with `--b-env`); `make test` names its tests.

## 3. S1: #1125

- [x] 3.1 Copy the S0 files into `../sf-ds4-1flash-base` (the S0 tree becomes A). Apply #1125 `a0fe413`, `2cf7986`, `a6fc294`, `6c41f9b` in order. Verify `make -j8` has no warnings and `make test-metal-ssd-experts` passes its three variants.
- [x] 3.2 The `6c41f9b` regression test (design D4) in `tests/test_metal_ssd_experts.c`, if the fixture reaches it in about 40 lines: GPU-copy seeds inside an open batch, a lower budget, the prune returns with the in-flight entries intact. Verify it passes on S1 and, with `6c41f9b` reverted in a scratch copy, hangs or fails (killed after 60 s). Otherwise write in the task line why it was not reachable. Not reachable: two GPU-copy seeds in one open batch pass with and without `6c41f9b` (256 entries both ways), because the second seed's load path waits for the in-flight entries (it commits the batch) before `prune_global` runs; only a thread that cannot wait (the `metal_graph` service thread, which V4.1 never runs) meets an in-flight victim there. The two-line guard stays with the rest of #1125.
- [x] 3.3 A/B S1 against S0 (`--a ../sf-ds4-1flash-base --b .`, D3 shape). Verify correctness PASS and no metric's CI wholly below zero. If pairs are dropped for cache drift, rerun with `--cache-policy-change` and record the drift next to the row.
- [x] 3.4 Short review of S1 (every `give_back` has a matching reservation; the GPU-copy install-failure path leaks deliberately, as upstream; no double return with `pending_load_release_buffers`); `make test` names its tests.

## 4. S2: read-ahead (design D7)

- [x] 4.1 Read-ahead off: `--a . --b . --b-env DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD=1`, D3 shape. Decide by design D2 (second pooled invocation only when the first is not a drop); a win makes read-ahead off the default by a constant change. Verify the decision and both invocations' rows are in the record.
- [x] 4.2 (Not needed: 4.1 dropped read-ahead off at decode 8192 -0.1%, append +300 +0.0%, ttft 5000 -0.2%; S2 has no code diff.) If 4.1 moved the default: `make -j8` no warnings, and one bench run with the timing summary shows `readahead_calls=0`. Verify the constant edit is the only code diff of S2.

## 5. S3: split reads (design D7)

- [x] 5.1 Refresh `../sf-ds4-1flash-base` with the S2 tree. Port `8f5a745` (`DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT`, default 1). Verify `make -j8` no warnings and `make test-metal-ssd-experts` passes with `DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT=4` set.
- [x] 5.2 Sweep split 4 (`--a . --b . --b-env DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT=4`), design D2; split 8 only if 4 wins, then pread threads 18 at the best split (split 4 raises a dispatch to about 13 tasks, so the 9-thread limit binds again and D7's reason to drop the thread sweep no longer holds). The best becomes the default; if none wins, revert `8f5a745`. Verify the pool line of one bench run shows the new `tasks_avg` (or the revert leaves S3's `git diff` empty).
- [x] 5.3 If S3 kept code: A/B the S3 tree against the S2 tree in `../sf-ds4-1flash-base` (D3 shape) as the step's own check. Verify correctness PASS and the gain agrees in sign with the sweep.
- [x] 5.4 Short review of S3 (split boundaries 16 KiB-aligned, per-task `ok` folded back, the fold keeps callers' byte counts); `make test` names its tests.

## 6. S4: residency

- [x] 6.1 Refresh `../sf-ds4-1flash-base` with the S3 tree. Port the `ds4_metal.m` part of `66f757b`. Verify `make -j8` no warnings and one bench run with `DS4_METAL_STREAMING_SLAB_RESIDENCY=1 --cache-stats` prints the `streaming slab residency:` line.
- [x] 6.2 Sweep it at `=1` (design D2). A win makes it the default with the switch `DS4_METAL_DISABLE_STREAMING_SLAB_RESIDENCY`, and adds `tests/test_metal_slab_residency.m` with its Makefile rule; otherwise revert. Kept by the owner's decision (2026-09-29) as an exception to D2: pooled decode 8192 -0.37% (CI -0.84..-0.10) lies wholly below zero, inside the band the start A/A produced on identical code (-1.1%), against first token 2048 +82.6%, first token 8192 +34.8%, ttft 5000 +1.87%, decode 2048 +1.35%, e2e +0.9%. Verify the record names the macOS version (`sw_vers -productVersion`) and the test, if added, runs from `make test`.
- [x] 6.3 Short review of S4 (the set is cleared before the slabs are freed and on mlock relief; the `@available` guard); `make test` names its tests.

## 7. Close

- [x] 7.1 Final pass over the regions the change touched, against `AGENT.md` and the surrounding idiom, deleting what the kept steps made dead. Verify `make -j8` no warnings, `make test` names its tests, `make test-metal-ssd-experts` passes.
- [x] 7.2 Record row: `git worktree add --detach ../sf-ds4-1flash-start 7dea5e3` (gguf symlink, `make -j8`), then the final tree against it, `--kinds decode,cold-2500,cold-5000 --guards guard-decode --bitwise` (the segment's kinds). Paste the row into segment 1 of `speed-bench/perf-record.md`. Verify its `decode 8192` gain is at least the `30` row's.
- [x] 7.3 Docs: `speed-bench/README.md` (`--b-env`, the pool line), `AGENTS.md` (every default this change moved and its switch), the registry lines of design D6, with the D7 drops (pread threads, slabs, slab size, `f7695ea`) as history. Verify `grep -n "b-env" speed-bench/README.md` and each moved switch name in `AGENTS.md` find their lines.
- [x] 7.4 Closing parity from the StarForge checkout: `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`. Verify `PARITY OK (10 prompts)`.
- [x] 7.5 Scope: `git diff main --stat` lists only `ds4_metal.m`, `ds4_gpu.h` if a step needed it, `tests/test_metal_ssd_experts.c`, `tests/test_metal_slab_residency.m` and `Makefile` if S4 was kept, `speed-bench/ab_bench.py`, `tests/test_ab_bench.py`, `speed-bench/README.md`, `speed-bench/perf-record.md`, `AGENTS.md`, `docs/upstream-prs.md` and this change's `openspec/` files; `git worktree list` shows only the checkout; `openspec validate 40-ssd-expert-reads --strict` passes.
