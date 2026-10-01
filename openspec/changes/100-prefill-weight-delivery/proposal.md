# Proposal

## Why

The explicit two-layer buffers introduced by `60` cover only non-wide sweeps up to 2048 rows, and their reader reloads complete layers even when expert bytes are already in the RAM cache. After the kernel work in `90`, improve the remaining weight-delivery stalls on the internal SSD before adding another disk.

## What Changes

- Extend explicit expert-buffer lifetime to wide sweeps without changing causal tile partitions, decoder suffixes, carry state or the admitted two-layer reserve.
- Independently assemble a layer from protected, ready RAM-cache entries plus reads of the absent ranges; preserve decode seeding and eviction behavior.
- Evaluate native Metal I/O as a separate, gated replacement for remaining pread/join overhead, not as an additional obligatory backend. Keep the existing reader if the native route is neutral or slower.
- Measure readiness waits separately from I/O already hidden behind GPU work. Never turn a transfer-rate improvement into an unmeasured TTFT claim.

## Capabilities

### New Capabilities
None. Same model, bytes, output, memory budget and supported configurations (`skip_specs: true`).

### Modified Capabilities
None. No change to the harness's fixed-cache or correctness contract.

## Impact

- `ds41_prefill_expert_*` and `ds41_graph_prefill_sweep` in `ds4.c`; narrow cache-copy, buffer-binding and optional Metal-I/O helpers in `ds4_metal.m` / `ds4_gpu.h`.
- Existing graph, streaming-cache and prefill tests; performance record and affected #952 registry lines if their code is reused.
- Requires the kept explicit-buffer step from `60`. If unavailable, stop and revise this proposal rather than reviving a rejected prerequisite.
- No extra layer buffer, larger expert cache, model sidecar, filesystem change or external SSD. `140` owns external prefill delivery.
