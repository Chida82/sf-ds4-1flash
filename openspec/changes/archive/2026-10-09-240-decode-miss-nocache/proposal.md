# Proposal

## Why

Decode misses are read by the pread pool with `pread(g_model_fd, ...)` on the cached model descriptor: four 16 KiB-aligned pieces per expert on 18 threads (`40`). Every miss therefore lands twice, in the page cache and in its cache slab, and at the harness hit rate (0.90, about 24 misses of 9.49 MiB per token) the page cache churns at the full read rate of the drive. Those pages displace what the page cache is useful for: the pageable decode statics (`200` measured up to 3.9 GiB of them evicted by a sweep), the Engram table pages and the KV files.

Prefill already reads its explicit layer buffers through a separate descriptor with `F_NOCACHE` (`ds41_prefill_expert_open_nocache_fd`), and the Engram tables are opened the same way (`ds4_engram.c`). Decode is the last cached reader of expert bytes. The Argodrive fork carries the same knob (`DS4_ARGODRIVE_PRIMARY_NOCACHE`) without a published measurement.

The effect can go either way. Today a miss on an expert evicted from the slab cache a short while ago is served from the page cache at memory speed rather than from the drive, and `110` found that the avoidable misses are exactly seeds and decode replacing each other. Uncached reads give that up. A one-hour A/B settles it.

## What Changes

- A second descriptor on the model path, opened when the engine hands over the model fd (`ds4_gpu_set_model_fd`), verified to name the same file (device, inode, size), with `F_NOCACHE` and `F_RDAHEAD 0`.
- The pread pool reads decode misses through it when `DS4_METAL_V41_DECODE_MISS_NOCACHE=1`, chosen per load so the decode-switch test can toggle it in one process. The `F_RDADVISE` warm-up that precedes a load is skipped in that mode: it would only fill pages the reads then bypass.
- Prefill, the `140` replica reads, mmap page-ins and Engram are untouched. A failed uncached read falls back to the cached descriptor for that piece, counted in the streaming summary.
- Output is unchanged by construction: the same bytes arrive in the same slot.
- Default off until measured; if kept, the default flips and the switch becomes `DS4_METAL_DISABLE_V41_DECODE_MISS_NOCACHE`.
- Expected: within about +/-1% on decode; the memory side (fewer pageouts, statics staying resident) is the more likely benefit and is reported with the row.

## Capabilities

### New Capabilities
None. Same results, different page-cache use (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: the descriptor's open and close, the pool's per-load choice, the readahead skip, the summary counters.
- `AGENTS.md` switch list; `speed-bench/perf-record.md`.
- Works the same with one drive or two: decode misses always read the model file.
