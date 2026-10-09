# Design

## Context

- **Budget.** Without `--ssd-streaming-cache-experts`, `ds4_engine_configure_streaming_cache_budget` (`ds4.c`) takes 86% of `ds4_gpu_recommended_working_set_size()` for model plus cache and prints it ("Metal recommends X GiB working set"). The harness passes `82GB`, so its runs skip that path: 74.88 GiB dynamic, 8078 slots of 9.49 MiB.
- **Wiring.** Cache slabs are mlocked (`ds4_metal.m`, the `mlock_budget_cap` relief caps the budget when `mlock` fails) and registered in a residency set; static weights are locked at open.
- **Idle in decode.** The prefill reserve (7.12 GiB, allocated per sweep) and, at ctx 32768, about 7.7 GiB of the 8.07 GiB context buffers (batch rows, carry rows, Engram prefetch, packed activation buffer).
- **Known figures.** `210` decode runs: used 114 GB of 137, available 23 GB (min 14.7), compressed 6.5 GB, swap 1.3 GB, pressure level 1. `145`: 4.0 miss layers per token, `pread` 0.667 ms per miss layer, about 7% of a token. Decode hit rate 0.90 at the harness cache, append 0.95.

## Goals / Non-Goals

**Goals:** one table per question (limits, timeline, miss source, miss curve) from one quiet session; a ranking of the memory levers by expected decode gain; the gates of `230` and `240` answered.

**Non-Goals:** any runtime change; changing `iogpu.wired_limit_mb` or any other sysctl; the external drive (`250`); prefill speed.

## Decisions

### D1. Order

1. Limits: a few `sysctl` reads and one engine open; seconds.
2. Timeline, miss source and id dump in the same runs, so the three tables share conditions.
3. Replay and ranking offline, on the CPU only.

Every run starts at thermal pressure Nominal and records it, like the harness rows.

### D2. The id dump

A scratch build (a worktree of the current `main`, never the tree under work) appends, at the decode expert load, the layer and the six selected ids of every token to a binary file. Harness-shaped runs: `decode 2048` and `decode 8192`, 256 tokens, and one `append`, with `--ssd-streaming-cache-experts 82GB`. The dump is written from a buffer flushed after the run, so its cost stays out of the measured tokens.

### D3. The replay

A scratch C program replays the dump through the victim policy as written in `ds4_metal.m` (decayed route hotness, decay every 16 tokens, protected entries, free slots claimed first), starting from the same popularity preload. It reports hits, misses and miss layers per token at each capacity. Acceptance: at 8078 slots it matches the run's measured hit rate within one point; otherwise the difference is traced before any other capacity is read.

### D4. Expected gain

A miss layer costs a `pread` wait whatever the number of misses in it, so the gain is read from miss layers, not misses: expected decode gain ~ (miss-layer reduction / miss layers per token) x miss share of the token (about 7%). The ranking lists, per lever, the bytes freed, the slots, the miss-layer reduction from the curve and the expected gain.

### D5. Levers and what decides between them

- **Wired limit**: admissible slots = min(the limit's headroom, the timeline's free memory at the prefill peak minus a margin for the rest of the system).
- **`230` S1** (lent slabs): 770 slots, no system memory cost beyond today's prefill peak.
- **Prefill-only context buffers**: if the timeline shows them resident during decode, `230` S2 lends them to the cache; if the cache cannot grow (limit reached), they are marked `MTLPurgeableStateVolatile` during decode instead, so the OS takes them without compressing or swapping. If they are already compressed, neither gains.
- **`240`**: the miss-source table gives the share of misses served from the file cache today; the timeline's file-backed pages give the memory it would return.

## Risks / Trade-offs

- The replay drifts from the real policy -> D3's acceptance at 8078 slots.
- Other applications move the timeline -> the session runs on a quiet machine, and the compressed and swapped pages are attributed per process with `footprint`.
- The dump perturbs the run -> buffered, flushed after; the timeline runs are not the throughput runs.

## Migration Plan

Branch `sf/225-mac-memory-evidence` from `main` after `220` lands; documentation and perf-record only. No commit or push without a request.
