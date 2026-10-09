# Tasks

## 1. Limits

- [x] 1.1 Read `hw.memsize`, `iogpu.wired_limit_mb`, `vm.global_user_wire_limit`, `vm.user_wire_limit` and, from one engine open without `--ssd-streaming-cache-experts`, the auto cache lines (`recommendedMaxWorkingSetSize`, model target, expert budget). Verify the auto budget printed matches 86% of the recommended size minus the non-routed weights (it does not: the context-aware cap, 7/8 of the recommended size less the context buffers, binds at 86 GiB; recorded); record the table in `speed-bench/perf-record.md`.

## 2. Timeline, miss source and id dump

- [x] 2.1 Scratch sampler (D1): `vm_stat`, `footprint` of the engine process and mactop's memory block once a second through engine open, a 5000-token prefill, 256 decode tokens and a second prefill, harness streaming flags. Verify the four phases are visible; record the table, with the prefill-only buffers' state during decode (resident, compressed, swapped) and the owner of the compressed and swapped pages.
- [x] 2.2 Scratch build in a worktree of `main` with a per-load `pread` histogram and the id dump (D2); runs `decode 2048`, `decode 8192` and `append`. Verify the dump holds 40 layers x 6 ids per token and the histogram's total equals the streaming summary's load count; record the share of loads under the drive latency.

## 3. Curve and ranking

- [x] 3.1 Replay program (D3) at 8078, +385, +770, +1050, +1600 slots. Verify the 8078 row is within one point of the measured hit rate; record hits, misses and miss layers per token per capacity.
- [x] 3.2 Ranking table (D4, D5): bytes freed, slots, miss-layer reduction, expected decode gain per lever, the order for `230` and `240`, and the `iogpu.wired_limit_mb` value the limit lever would need. Update `docs/MacM5.md` with the limits; `openspec validate 225-mac-memory-evidence --strict`. No commit or push without a request.
