# Design

## Context

See proposal.md. `ds41_prefill_expert_sweep_supported` excludes wide, encoder-only and resume sweeps. Its two slots already consume the admitted 7.12 GiB reserve. `ds41_prefill_expert_read` reads gate/up/down into shared Metal buffers; decode uses a separate file descriptor/cache path. The explicit cache holds about half the routed bytes, but that is not a guarantee of half the I/O saved.

## Goals / Non-Goals

**Goals:** reduce exposed layer-ready waits without changing the rows evaluated or increasing the allocation ceiling.

**Non-Goals:** reduce token-major tails by rebatching them, add a third layer buffer, spend recovered RAM on more expert slots in the benchmark, or change the prefill seeding policy. External sources belong to `140`.

## Decisions

### D1. Prerequisite and gate

Start after `90` is resolved and only if `60`'s explicit-reader path was kept. On the accepted baseline, attribute map/read wait, encode/drain and seed time for `cold-2500,3500,5000,7500,10000` and append +1500. Profile labels already exist in `ds41_graph_prefill_sweep`. A zero exposed-I/O opportunity closes the relevant stage; no neutral infrastructure is retained to enable `140`.

### D2. Extend lifetime, not schedule

A slot remains bound from a layer's first decoder preparation through all its tiles and cache seeding. Its previous reader must finish before binding, and all GPU consumers/blits must finish before the slot is reused two layers later. Start the next layer's read only into the other safe slot. Keep `ds41_encoder_chunk_cap`, `first`, warm rows, carry-copy and decoder-suffix arithmetic unchanged.

First cover ordinary wide sweeps, including shrinking decoder tails. Encoder-only/resume continues on the existing path unless that exact lifetime is separately proven and measured; do not simply remove every gate. Existing TP, quality and resident exclusions stay. Failure invalidates the partial sweep as today, joins readers, drains dependent work and frees only owned resources.

### D3. RAM first with unchanged cache semantics

On the encoding thread, find ready, non-in-flight entries for the next layer without recording a decode hit or updating recency/hotness. Copy their immutable quantized gate/up/down bytes into the destination slot using existing GPU-copy machinery; retain/protect sources until the copy completes. Do not read or mutate the cache from a disk worker. The destination is ready only after both RAM copies and disk reads complete.

Build missing disk ranges in original file order, coalescing adjacent misses without rereading RAM hits. Selected sources remain protected against seeding/recycling; release protection at the copy completion boundary, not at enqueue. If preserving the cache policy/lifetime cannot be proven, drop this step. Adding a new pin must not repurpose decode counters or silently change victim selection.

Keep the dynamic slot count, reserve and numerical buffers unchanged. Report RAM-copy bytes and physical-source-request bytes separately; their sum covers the requested layer exactly. Fragmentation can make selective reads slower, so byte savings alone are not a keep verdict.

### D4. Native I/O only for a remaining cost

If waits/host scheduling still matter, trial `MTLIOCommandBuffer` for the same missing ranges and same buffers. One IO queue and shared-event generations express producer/consumer readiness; existing compute submission remains unchanged. Do not call `waitUntilCompleted` immediately after each load and call it overlap. Use availability checks and the existing pread path when the native API is unavailable.

Before binding a destination, validate IO status. On failure/cancel, settle outstanding IO and GPU consumers before freeing/retrying any buffer. An error does not authorize fallback into storage still being written. The native route must satisfy the same engine error semantics and win independently; otherwise remove it. No new general-purpose storage abstraction or compressed asset format.

### D5. Evidence

Extend `test_deepseek41_graph`'s synthetic explicit-read fixture with multi-tile lifetimes, reuse, early EOF and cancellation. Add cache-source tests with in-flight entries, eviction pressure and delayed copies. Compare raw layer bytes and full-session logits/state bitwise. A fake read/copy completion fixture provides deterministic failure coverage without unplugging hardware.

Judge each stage using the normal `cold,append` harness (not section timing, because overlap changes), with timed decode checks and both long guards. Use identical admitted slots; keep default cache-state checks while policy is unchanged. Final review, segment-start row and upstream parity follow, verifying the oracle targets this candidate. Update #952 provenance/verdicts only if its work is acted upon.

## Risks / Trade-offs

- RAM copies compete with compute -> count copy duration and use uninstrumented wall time.
- Longer slot lifetime collides with layer-20 preparation -> test decoder suffix and cancelled/retried sweeps explicitly.
- Warm page cache hides disk effects -> retain warm baseline behavior and report source counters; do not purge system caches.
- Extra bookkeeping exceeds the benefit -> project keep/drop gate, including the larger-step threshold.

## Migration Plan

Use `perf/100-prefill-weight-delivery`; each accepted stage is the next stage's baseline. Keep safe fallbacks and remove failed trials. No new user-facing option or file format; rollback restores the previous reader. Do not modify OS limits, mount options or software installations.
