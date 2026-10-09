# Proposal

## Why

macOS manages memory by kind: wired pages stay, anonymous pages are compressed then swapped, clean file pages are dropped, purgeable pages are taken back without either. The engine already declares the hot data correctly: the expert cache slabs are mlocked and in a residency set, the static weights are locked (9.37 GiB, pageable 0), the explicit prefill layer buffers are set `MTLPurgeableStateEmpty` on release, and Engram and the prefill buffers read through `F_NOCACHE` descriptors.

Three areas are not declared, and nothing measured says what they cost:

- **The GPU working-set limit.** The auto cache budget is 86% of `recommendedMaxWorkingSetSize` (`ds4_engine_configure_streaming_cache_budget`), which macOS derives from the GPU wired limit (`iogpu.wired_limit_mb`). During the `210` decode runs 23 GB were still available (minimum 14.7). If the limit, not the RAM, caps the cache, about 1000 more slots (+13%) are possible without code.
- **Prefill-only memory during decode.** The 7.12 GiB reserve and about 7.7 GiB of prefill-only context buffers sit idle through every decode token as ordinary memory, which the OS may compress or swap. `230` lends the reserve to the cache; marking them volatile would hand them to the OS instead.
- **Decode misses through the file cache.** The pool reads misses on the cached model descriptor, so a miss's bytes can sit both in the file cache and in a slab. `240` reads them uncached.

What each lever is worth depends on how many misses a larger cache removes, and there is no curve of misses against cache size today: `230` and `240` each open with their own gate measurement. This change takes those gates and the two missing measurements into one session, so the levers can be ranked before any of them is coded.

## What Changes

Measurement only, no runtime code. The external drive is not needed.

- **Limits.** `hw.memsize`, `recommendedMaxWorkingSetSize`, `iogpu.wired_limit_mb`, `vm.global_user_wire_limit`, `vm.user_wire_limit`, and the auto cache lines of one engine open without `--ssd-streaming-cache-experts`.
- **Memory timeline** (from `230` D1). Once a second through engine open, a 5000-token prefill, 256 decode tokens and a second prefill: `vm_stat` (free, file-backed, compressor pages, compressions, decompressions, swapins, swapouts), `footprint` of the engine process, and mactop's memory block.
- **Miss source** (from `240` D4). A per-load `pread` time histogram during decode; loads well under the drive latency are file-cache hits.
- **Miss curve.** A scratch dump of the selected expert ids per layer and token during harness-shaped decodes, replayed on the CPU through the cache's victim policy at the harness capacity (8078 slots) and at +385, +770, +1050 and +1600 slots. The replay at 8078 must match the measured hit rate within one point.
- **Ranking.** For each lever (wired limit, `230` S1, `230` S2 or volatile buffers, `240`), the slots or bytes it frees, the misses removed from the curve, and the expected decode gain from the miss share of a token. The table sets the order of `230` and `240`.
- `speed-bench/perf-record.md` gets the section; `docs/MacM5.md` gets the limits.

Any change of `iogpu.wired_limit_mb` is outside this change: it needs `sudo`, does not survive a reboot, and is the user's to run. The ranking states the value it would need and the headroom left.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `speed-bench/perf-record.md`, `docs/MacM5.md`.
- `230-expert-cache-growth` and `240-decode-miss-nocache` read their gates from this change instead of measuring them.
- The id dump and the replay live in the scratchpad; the engine tree is not changed.
