# Proposal

## Why

After `70` and the kernel/memory work through `120`, CPU pipeline lookup and command submission may account for an actionable part of the remaining GPU idle time. The old `sync` counter includes real GPU computation, so it cannot justify a wholesale Metal 4 migration or a GPU-driven cache scheduler by itself.

## What Changes

- Attribute actual CPU encode/allocation time and GPU gaps using existing diagnostics, with separate uninstrumented timings.
- Extend the existing allocation-free pipeline lookup to the remaining measured hot getters; reuse cached pipeline objects rather than add another abstraction.
- If gaps remain, test coalescing only adjacent command-encoding segments that have no CPU readback, live-buffer reuse or cancellation boundary between them.
- Keep the existing streaming selected-ID synchronization and in-flight cache safety. Record Metal 4 submission and GPU-driven all-hit continuation as gated alternatives requiring a follow-up design, not an automatic rewrite in this change.

## Capabilities

### New Capabilities
None. Submission implementation only (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m` pipeline lookup and batch-encoder handling; a narrow `ds4.c` call-site adjustment only if a measured boundary can safely coalesce.
- Existing command-memory, graph queue and streaming-cache tests, plus performance record and the #1067 `d1738d2` verdict.
- Do not repeat the slower flush-every-second-layer variant rejected in `30`, disable hazard tracking globally, spin indefinitely on a GPU miss, move inference to CPU/ANE, or add C++.
- This closes single-device software investigations before the optional external-storage changes `140` and `150`.
