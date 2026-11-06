# Proposal

## Why

Upstream `55b1e75`, one of the narrow-copy commits the `b3f5018` sync took,
also made Metal hazard tracking off by default for V4.1's model weights:
the mmap model views, the exact-range views and the narrow decode copies are
created with `MTLResourceHazardTrackingModeUntracked`, and
`DS4_METAL_MODEL_TRACKED=1` restores tracking. `890898c` and `9fe88cd` then
made the default actually apply (before them the setter ran before the model
family was known). The sync took the copies but not this default.

This child still tracks by default: `ds4_gpu_model_resource_options`
(`ds4_metal.m`) goes untracked only when `DS4_METAL_MODEL_UNTRACKED` is set,
the narrow copies are always tracked, and nothing here has measured either.
Hazard tracking makes Metal order GPU writes against later reads. The weights
are never written by the GPU: the model mmap is `PROT_READ`, and the copies are
filled by the CPU once before their first use. So tracking them costs
encoding work for nothing, and the output cannot change.

Upstream gives no figure for the default. In streaming the token is bound by
SSD reads, so the gain may be below resolution; the change is small enough
that a measurement decides it.

## What Changes

- Model views and exact-range views untracked by default, as upstream:
  `DS4_METAL_MODEL_TRACKED=1` restores tracking. `DS4_METAL_MODEL_UNTRACKED`
  is removed (it becomes the default).
- The narrow decode copies allocated with the same options, through a weights
  allocation entry like upstream's `ds4_gpu_tensor_alloc_weights`.
- The expert cache slabs, the explicit prefill buffers and every buffer the GPU
  writes stay tracked.
- No output change.

## Capabilities

### New Capabilities
- `metal-weight-tracking`: which Metal buffers are created without hazard
  tracking, why that is safe, and the switch that restores tracking.

### Modified Capabilities
- None.

## Impact

- Code: `ds4_metal.m` (`ds4_gpu_model_resource_options`, a weights allocation
  entry), `ds4_gpu.h`, `ds4.c` (the narrow-copy allocations), `ds4_env.def`.
- Tests: a two-process bitwise check (the engine creates the views at open, so
  `make test-deepseek41-decode-switch`, which toggles the switch inside one
  open engine, cannot see it); `make test`.
- Docs: `AGENTS.md` (narrow copies paragraph), `docs/upstream-prs.md` (the
  `890898c`/`9fe88cd` row and the `55b1e75` note), `speed-bench/perf-record.md`.
