# Proposal

## Why

In streaming decode every layer still stops at the selected-id readback. After `131` and `132` the CPU learns the six router ids only when the router's command buffer reports `Completed`, about 44 us after the GPU finished it (`132`'s probe: wake 43.6 us, GPU idle before the expert pass 121.6 us per all-hit layer), and the shared expert has to live in a second command buffer so that wait does not cover it. The ids themselves are six integers the router kernel has already written. The Argodrive fork of ds4 (`argonautlabsai/ds4-argodrive`, `9ad4a61`, `DS4_ARGODRIVE_FLAG_READBACK`) publishes them from inside the running command buffer into a shared-memory mailbox the CPU polls, and measured +6.6% steady decode against a blocking readback on V4.1 Q4. The gate probe of this change measured the property it relies on: a GPU store in shared memory is visible to the CPU about 20 us after its command buffer's GPU end, 25-30 us before the status turns `Completed`. It is the command buffer's end that publishes, not the kernel's: a store followed by more work in the same command buffer arrives only after that work.

## What Changes

- `132`'s split stays: the router's batch is still committed alone, and its last dispatch becomes a one-thread kernel that copies the selected ids, a checksum and a sequence word into a 64-byte shared buffer. The shared expert keeps its own batch.
- At the readback the shared-expert batch is committed and the CPU polls the mailbox instead of the router batch's status (bounded; `131`'s status poll and the tensor read remain as the fallback). The expert pass is encoded and committed as soon as the ids arrive.
- The router batch stays pending; the buffers committed before it are waited (they ended before it started, so this does not block) and the expert cache's done sequence moves to just below the router batch's sequence. The router batch holds no expert-cache entry, so the cache sees the same in-flight set as today.
- Same kernels, same inputs, same ids: output stays bitwise. Rollback switch `DS4_METAL_DISABLE_V41_READBACK_MAILBOX`, checked by `make test-deepseek41-decode-switch`; with it set, the `131`/`132` path runs unchanged.
- Expected: the expert pass commits about 25 us earlier per layer (wake 44 -> about 20 us), about 1 ms of a 44 ms token (2-2.5%); the GPU restart (about 100-115 us from commit to start, `132`) is the floor that remains.

## Capabilities

### New Capabilities
None. Same results, different submission (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: `ds41_moe_partial` passes the selected tensor to `ds4_gpu_split_readback` (single streaming box only, as today).
- `ds4_metal.m`: the publish inside `ds4_gpu_split_readback`, the mailbox poll and the partial wait in `ds4_gpu_commit_split_wait_pending`, the skipped tensor read in `ds4_gpu_routed_moe_one_tensor`, a hit/fallback line in the streaming summary. `metal/dsv41.metal`: one kernel. `ds4_gpu.h`: one signature.
- `docs/upstream-prs.md`: the mechanism's provenance (Argodrive is not an upstream PR; the code is written here).
- Builds on `131` and `132`; `145`'s split-deferred path is untouched (it lives in the expert pass encode). No external SSD. TP (`tp_world == 2`), resident decode, prefill sweeps and token-major tails are not changed.
