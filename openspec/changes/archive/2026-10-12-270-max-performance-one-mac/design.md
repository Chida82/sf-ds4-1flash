# Design

## Context

- **The cap.** `ds4_streaming_manual_cache_safe_bytes` (`ds4.c`) caps an explicit cache flag at `floor_GiB(7/8 x recommended - context buffers)` and prints `cache budget ... capped to ...`. The context buffers come from `ds41_graph_bytes(ctx)`. From the engine's own estimate:

  | ctx | buffers | cap today (107.52 GiB recommended) |
  |---|---|---|
  | 32K | 7.89 GiB | 86 |
  | 256K | 10.38 GiB | 83 |
  | 1M | 18.92 GiB | 75 |

  The KV itself is 6.4 KB per token (1.56 GiB at 256K); the rest is fixed prefill storage.
- **The flag.** `NGB` is GiB in total. The loader takes the 7.12 GiB prefill reserve first, and the rest becomes 9.49 MiB slots: `82GB` gives 8078 slots, and about 108 slots per extra GiB.
- **The static weights.** They are 9.37 GiB, locked only when they fit the same capped budget beside the cache. At `82GB` they already stay pageable (`225`).
- **The harness.**
  - `ab_bench.py` fixes `CACHE_FLAG = '82GB'`, `CACHE_WINDOW = (74.5, 75.5)` and `CTX_ALLOC = 32768`, and stops a run whose loader line falls outside the window or whose context line differs.
  - `--env` already reaches both builds, so the copy needs no new option.
  - The harness never passes `--boost`.
- **The replay.**
  - The `225` replay (`replay.c`, dumps `dump_decode.txt` and `dump_append.txt`) lives in a session scratchpad. If it is gone, the scratch id-dump build of `225` task 3.1 regenerates it.
  - The replay matched the measured hit rate exactly at 8078 slots.
  - It gave decode miss layers per token of 3.91 (8078 slots), 3.33 (+385), 3.07 (+770) and 3.07 beyond, and append 4.05, 3.52, 3.05, 2.81 (+1050) and 2.45 (+1600).

## Goals / Non-Goals

**Goals:**
- One cache value and one `iogpu.wired_limit_mb` value, chosen by measurement, for a 256K context with at least 18 GiB left to macOS.
- A README recipe anyone can rerun.

**Non-Goals:**
- Changing the default cache, the auto budget, or the cap formula.
- Filling a 256K context: the context is allocated, and the prompts stay harness-sized.
- Values above 90 GiB, which break the 18 GiB rule.
- Running the ceiling test itself: its results table is left for the owner.

## Decisions

### D1. The memory frame
macOS keeps `128 - C - 10.38 - 9.37` GiB, so C is at most 90.25 and the candidates are 86, 88 and 90. Below 86 the gain over the cap of today is under one interval of noise. 92 leaves 16.25 GiB.

### D2. One working-set limit per session
The owner sets `iogpu.wired_limit_mb` once, for the largest candidate, and every arm runs under it. The cap does not bind the smaller arms.

The value is `(C + 10.38) x 8/7 + 0.5` GiB, in MiB rounded up to the next 100:
- 90 → 118000;
- 88 → 115700;
- 86 → 113400.

The 0.5 GiB margin keeps the floor from cutting the flag if Metal reports the limit slightly under the sysctl value.

The first task reads the reported recommended size back, so the margin is checked, not assumed. The limit is a ceiling, not an allocation, so the 82 arm uses the same memory as in normal use. The alternative, one sysctl per arm, needs the owner at every switch and gains nothing.

### D3. Harness options, not a fork of the harness
- `--b-cache NGB` sets B's flag. For B, the window becomes `NGB - 7.12 GiB` ± 0.5.
- `--ctx-alloc N` replaces `CTX_ALLOC` for both builds.
- A `capped to` line in either build's stderr stops the run with exit 2, because the cache would not be the one asked.
- The defaults reproduce today's invocation exactly.
- An A/A with `--b-cache 82GB` is the tool step's check: bitwise, and no metric below zero.

The alternative, `--b-bench-arg` with a second `--ssd-streaming-cache-experts`, relies on the last flag winning and still trips the window, so it was rejected.

### D4. What is measured
- **The replay first.** It runs on the CPU and needs no machine time. If 88 and 90 replay identically on both kinds, 90 runs only as the memory check.
- **The A/B.** Each candidate is a B arm against A = `82GB` on the same tree:
  - kinds `decode,append`, guards `guard-16896,guard-decode`;
  - `--bitwise --cache-policy-change --ctx-alloc 262144`;
  - `--env DS4_METAL_PREFILL_REPLICA=<copy>`.

  The copy matters here: a larger cache shrinks the file cache, which is where the copy's first-token advantage after a sweep comes from (README, "A second drive").
- **The memory check.** One `225`-style timeline run of the chosen value: open, prefill 5000, 256 decode tokens, prefill 10000, 256 decode tokens, at `--ctx-alloc 262144`. It records:
  - `vm_stat` once a second;
  - `footprint` every 3 s;
  - mactop's memory block.

  It passes with zero swapouts, none of the engine's pages compressed, and the minimum available memory reported.

### D5. The choice
- **The target** is the pooled decode gain, then the append gain. The first token after the 8192 prefill and the guards must not have a CI wholly below zero.
- **The smaller value wins** when the next larger one's gain lies within its interval, because it leaves more to macOS.
- **The result row** goes to `perf-record.md`. The test is named `max_performance_<C>`.

### D6. The README section
It sits after "A second drive". It holds:
- the commands: `sudo sysctl iogpu.wired_limit_mb=<W>`; the bench with the copy, `--boost`, `--ssd-streaming-cache-experts <C>GB`, `--ctx-alloc 262144`, and the "Against ds4" sweep (2048 to 32768 doubling, 128 tokens); then the reset `sudo sysctl iogpu.wired_limit_mb=0`;
- a precondition: a cool machine with `fanboost` running;
- the reason for each value, from D1 and D4;
- a log check: no `capped to` line;
- a table with the "Against ds4" rows and columns `82GB` and `max_performance_<C>`, every cell empty.

The `82GB` callout under "Speed" links to the section. A provisional section written during planning sits uncommitted in the working tree, and this task rewrites it.

### D7. The cache is locked at engine open
The first `86GB` A/B stopped on a token difference. In that one run the cache's mlock failed with EAGAIN after 78.54 of 78.88 GiB, and the engine shrank the cache to 7619 slots, fewer than `82GB`'s 8078. The working-set limit was not the cause. The binding limit is `vm.global_user_wire_limit`:
- it is 108.8 GiB, that is 128 GiB less the kernel's 19.2 GiB reserve;
- it counts every wired page, the GPU's included;
- `iogpu.wired_limit_mb` does not move it.

The slots are mlocked one by one as `ds41_prefill_seed` fills them during the first prefill. At that moment the prefill's explicit expert buffers (7.12 GiB) and its scratch (+7.3 GiB) are wired too. Other wired memory at the failing lock was 26.5 to 32.8 GiB, against about 21 GiB at engine open. Two first-prompt tests at 16896 tokens, on a clean start:
- `90GB` failed at 75.97 GiB and fell to 7367 slots;
- `86GB` and `88GB` passed, with peaks of 105.39 and 102.17 GiB.

Raising `vm.global_user_wire_limit` would take its margin from the kernel and needs another `sudo`, so it is not used. Instead, the engine allocates every slab at open and mlocks every slot before any prefill (`ds4_gpu_stream_expert_cache_lock_ahead`). The locked slots go on the free list, which the lazy path already serves first. `DS4_METAL_DISABLE_STREAMING_CACHE_LOCK_AHEAD=1` restores lazy locking. It runs for single-box streaming only.

With the change, `90GB` locks 8941 of 8941 slots at open in 2.1 s, and the peak wired is 104.95 GiB. The A/Bs of D4 run on this tree. The change itself is checked at `82GB` against `main` (`decode,append,cold-5000`, `--bitwise`): it must not worsen. The harness also stops on `using locked cache cap` with exit 2, as it does on `capped to`.

## Risks / Trade-offs

- [Metal does not follow `iogpu.wired_limit_mb` one to one] → the first task reads the recommended size back; the margin of D2 absorbs a small difference, and a larger one changes W before any run.
- [18 GiB is too little for the owner's apps during a long session] → the memory check reports the minimum available; the owner can pick the next smaller candidate from the same table.
- [The `sysctl` outlives the session if the owner forgets the reset] → it does not survive a reboot; the README and the task list end with the reset.
- [A/B noise at about 1%] → the inconclusive rule of the project: one repeat with a longer budget on the deciding kinds.
- [The copy's drive is not mounted] → the engine refuses to start; the session waits for the owner.
- [Locking at open costs time and commits memory before it is used] → about 2 s at open for 83 GiB. The cache fills within the first prompt anyway, and the first prefill no longer pays the mlock.
- [Output under the old fallback] → the run where the lock failed decoded different tokens (frontier 5000, token 11). The fallback is not investigated here. Locking at open removes its trigger up to `90GB`.

## Migration Plan

1. Branch `sf/270-max-performance-one-mac` from `main`.
2. The harness tool step lands with the change.
3. Nothing runtime changes, so there is no rollback.
4. No commit or push without the owner's request.
