# Design

## Context

- Engine open under streaming (`ds4.c`, after `ds4_gpu_set_streaming_expert_cache_budget`)
  already tries to `mlock` the decode-static spans when they fit the safe budget
  next to the expert cache. At `82GB` they do not, and the loader prints
  "static weights remain pageable to preserve runtime headroom". Then
  `ds4_gpu_stream_expert_cache_lock_ahead` wires every cache slot (74.46 GiB in
  about 1.9 s), and the kernel evicts file pages to make room.
- Expert and Engram reads use `F_NOCACHE`, so the engine itself does not refill
  the file cache with them. The static weights are reached only through the
  model mapping (CPU) and its no-copy Metal views (GPU).
- With the narrow decode copies (sync `b3f5018`), the decode reads 0.96 GiB of
  copies instead of the router F32, the Engram projection F16 and the indexer
  q_b F16; the prefill still reads the wide tensors.
- Evidence (2026-11-06, `perf-record.md` gets it with this change): with the
  start state fixed by `purge` plus a read of every static tensor, main and
  copies-off ran 161.8 and 161.0 t/s, and only about 60 pages were paged in. In
  back-to-back runs, main paged in up to 1.4 GiB (13 s of fault waits) and the
  router F32 fell from 300 to 125 MiB resident before its prefill. Evicting the
  router F32 alone from a copies-off run did not slow it (168 and 174 t/s): the
  slow state is the whole set of pages a previous process left cold, not one
  tensor.

## Goals / Non-Goals

**Goals:**
- The first prefill of a fresh process runs as if the static weights were
  cached.
- Know, by measurement, whether a long-lived process meets the same faults, and
  fix that case only if it does.

**Non-Goals:**
- Locking all 9.4 GiB of static weights. The existing lock path does that when
  the budget allows; making it fit at `82GB` would shrink the expert cache by
  9.4 GiB.
- Protecting the static weights against other processes' file I/O beyond what
  the kernel's page ageing gives. That is the owner's machine, not the engine.

## Decisions

- **Measure the server regime before changing anything for it.** A bench run
  with frontiers has a different shape from a server, so the test uses one
  process with two prompts: `sf-ds4-1flash-server` and two requests through its
  API (prompt A, 2000 generated tokens, then prompt B, unrelated so no KV
  reuse). The test records `fs_usage` page-ins and page-cache snapshots of the
  static tensors around request B. It runs with the copies on and off, and once
  more with 20 GiB of unrelated file reads between the two requests.
  *Alternative:* argue it from the code (statics untouched by decode age out
  only under file-cache pressure). This is likely, but the prefill reserve's
  explicit layer buffers may be allocated per prefill, which would force
  eviction at every prompt, so it is measured instead.
- **Prefault, not lock, for the fresh process.** After the lock-ahead, touch
  the decode-static spans (`POSIX_MADV_WILLNEED` followed by one read per
  page, bounded per call as the lock loop does). This brings the static
  weights in before the first prefill. It adds no wired memory and costs
  nothing when the pages are already cached. Cold, it reads 9.4 GiB at SSD
  speed (about 1.5 s) instead of faulting it page by page during the prefill
  (about 5 s on 2048 tokens). *Alternative:* `WILLNEED` alone. It is only a
  hint and does not order the reads before the prefill, so it is kept
  only if it measures the same.
- **Lock the skipped wide weights only if the server test needs it.** If it
  does, `mlock` the router F32, Engram projection and indexer q_b spans
  whenever their narrow copy exists, and take their 0.96 GiB out of the cache
  target, as the copies' reservation already is. The decode gives these pages
  no access, so ageing alone would evict them. *Alternative:* lock all statics.
  Rejected above (Non-Goals).
- **Switches.** `DS4_METAL_DISABLE_STREAMING_STATIC_PREFAULT` and, if the lock
  lands, `DS4_METAL_DISABLE_V41_WIDE_LOCK`, both `disable` in `ds4_env.def`.

## Risks / Trade-offs

- [A measurement artefact] The fresh-process gap exists only between processes.
  A long-lived server may never see it. → The server test decides whether the
  lock part exists at all; the prefault still fixes the README and
  fresh-process numbers, which the harness reports.
- [Engine-open time] Cold, the prefault adds about 1.5 s to engine open. → It
  is counted in the cold-start scenario (open to end of the first prefill), not
  hidden.
- [Wired-limit headroom] Locking 0.96 GiB more wires it under
  `vm.global_user_wire_limit` (108.8 GiB). Measured wired memory during prefill
  is 92-97 GiB. → It is taken out of the cache target, so the planned total
  does not grow.
- [Noise] Fresh-process prefill varies from 133 to 175 t/s with the inherited
  state. → Fix the start state for the A/B: `purge` plus a static read for the
  reference, back-to-back for the scenario.

## Migration Plan

Land as one commit after the A/B. Rollback is the switches or a revert.
