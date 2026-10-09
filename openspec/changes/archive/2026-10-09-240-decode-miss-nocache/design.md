# Design

## Context

- The pool worker reads each piece with `pread(g_model_fd, dst + pos, want, offset + pos)` (`ds4_metal.m`, `ds4_gpu_stream_expert_pread_pool_*`); `g_model_fd` is set once by `ds4_gpu_set_model_fd(e->model.fd)` from `ds4.c` and is also the descriptor behind the mmap model views.
- Before a load, `F_RDADVISE` is issued on the same descriptor for the expert's ranges (the readahead counted in the timing summary).
- `ds41_prefill_expert_open_nocache_fd` (`ds4.c`) is the pattern: `F_GETPATH` on the source fd, `open`, compare `st_dev`/`st_ino`/`st_size`, then `F_NOCACHE`. It is static to `ds4.c`; the Metal side gets its own copy of the same twelve lines rather than a new cross-file export.
- On APFS, `F_NOCACHE` bypasses the unified buffer cache for page-aligned I/O and still caches the unaligned head and tail of a read. The pool's pieces are 16 KiB-aligned, so the reads are fully uncached.
- The decode-switch test toggles environment variables inside one process, so the switch is read with `getenv` per load, not cached.

## Goals / Non-Goals

**Goals:** decode miss reads that leave no pages behind; no change to any other reader; output bitwise; a measured yes or no.

**Non-Goals:** direct I/O for prefill mmap page-ins or the deferred-decoder sweeps, changes to the pool's split or thread count, the replica reader, Engram.

## Decisions

### D1. A second descriptor, not a flag on `g_model_fd`

`F_NOCACHE` is a property of the open file description; setting it on `g_model_fd` would also strip caching from the mmap views and any other reader on that fd. A separate descriptor keeps the scope to the pool. Alternative, toggling the flag around each read: two syscalls per piece and a race with other readers; rejected.

### D2. Scope: the pool's decode miss reads

The pool is the only reader changed. Prefill explicit buffers already use a nocache descriptor, Engram opens its tables uncached, mmap page-ins stay on the cached mapping. The choice is made per load from the switch, both descriptors staying open for the session; the uncached one is closed at cleanup.

### D3. Readahead

With the switch on, the `F_RDADVISE` call before a load is skipped: advising the cached descriptor would read the pages into the cache the uncached `pread` then bypasses, doubling the drive traffic. Its timing counters stay at zero in that mode.

### D4. What the measurement reads

- Throughput: harness `decode,append` with `guard-16896,guard-decode`, `--bitwise`, against the previous kept tree. Hit rates are identical by construction (the slab cache policy is untouched), so no `--cache-policy-change`.
- The cost side, before the A/B, from `225-mac-memory-evidence`: a per-load `pread` histogram; loads well under the drive's latency are page-cache hits. Their share of misses today is the ceiling of the loss.
- The memory side, during the A/B: `vm_stat` pageouts and pageins once a second, and the first token after a sweep (where `200` saw the statics reload).

### D5. Default

Off until measured. If the keep rule holds, the default becomes on and the switch is renamed to the disable form in the same step, so the decode-switch test keeps covering it.

## Risks / Trade-offs

- Page-cache hits on recently evicted experts disappear -> measured first (D4); the A/B decides.
- An uncached read fails on some path or offset -> that piece is re-read through the cached descriptor, counted and printed.
- `F_RDAHEAD 0` and `F_NOCACHE` on a file another process is reading -> they are per-description, so other readers are unaffected.
- Two descriptors on the model file -> both closed at cleanup; the replica check and the lock file are unaffected.

## Migration Plan

Branch `perf/240-decode-miss-nocache` from `main`; it can also run as an extra arm inside the `230` measurement session. The switch joins the decode list in `AGENTS.md`. No commit or push without a request.
