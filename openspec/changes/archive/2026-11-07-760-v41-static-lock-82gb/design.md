# Design

## Context

- Engine open (`ds4.c`, before the expert-cache lock-ahead) locks the static
  spans when `static_bytes <= budget && experts <= budget - static_bytes`,
  where `budget = ds4_streaming_manual_cache_safe_bytes(...)`. That is 7/8 of
  `ds4_gpu_recommended_working_set_size()` less the context buffers, floored
  to whole GiB. At `82GB` and 32K, experts (74.40 + 7.12 GiB) plus statics
  (9.37 GiB) exceed it, so the statics stay pageable.
- The real ceiling for locked memory is `vm.global_user_wire_limit` (108.8
  GiB on this machine). It counts the expert cache, the GPU's wired pages
  and every `mlock` (AGENTS.md, SSD streaming).
- Upstream counts the total for Qwen only (`81ee4ba`: statics, cache, graph
  and staging under the smaller of 87.5% of RAM and the working-set
  recommendation). Open upstream PR #499 locks the same spans behind an
  opt-in switch.
- With pageable statics and free memory at the floor, every command batch
  waits about 290 ms for the kernel to wire their pages. That costs 3 s on a
  2048 prefill, and about 5% in back-to-back sweeps (proposal table).

## Goals / Non-Goals

**Goals:**
- Lock the static weights at `80GB` and `82GB` (32K to 256K contexts) when the wire
  limit allows. Show that it costs nothing elsewhere.

**Non-Goals:**
- Changing the expert-cache size or the `82GB` measurement configuration.
- Locking anything beyond the decode-static spans the lock already covers.

## Decisions

- **Decide by the wire limit, not by 7/8 of the working set.** Add a second
  admission path for the static lock. Lock when the planned wired total
  (expert cache, prefill reserve, context buffers, statics, narrow copies)
  plus a margin stays under `vm.global_user_wire_limit` read with
  `sysctlbyname`. The margin covers the GPU's transient wiring measured at
  the peak, about 2.5 GiB over the plan at 256K. The existing 7/8 path is
  kept: whichever allows the lock wins. *Alternative:* lower the 7/8 factor.
  That is a working-set argument for the cache size, not for wiring, and it
  would also move the cache cap that `ds4_streaming_manual_cache_safe_bytes`
  sets.
- **Fallback.** If `mlock` fails part-way, the existing loop stops locking
  and reports "pageable X GiB", and `750`'s prefault runs on the rest
  (`statics_pageable = failed > 0`).
- **No new switch.** `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK` already turns
  the lock off, and `750`'s prefault then applies.

## Risks / Trade-offs

- [Token-major prefill near the working set] The upstream comment on the
  safe budget. → Run the harness `append` (+300, token by token) and
  `cold-2500,cold-7500`, A/B against `main`+`750`, and a 256K CLI session.
- [Wire limit on other Macs] The limit differs per machine. → The check reads
  it at runtime and falls back to pageable.
- [File cache during decode] 9.37 GiB fewer pageable bytes. Decode reads
  experts with `F_NOCACHE`, and the statics would be locked. → Harness
  `decode` A/B.

## Migration Plan

One commit after the A/B. Rollback: `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK=1`
or a revert.
