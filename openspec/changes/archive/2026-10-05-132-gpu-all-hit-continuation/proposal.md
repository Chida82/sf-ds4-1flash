# Proposal

## Why

In streaming decode the GPU idles about 12 ms of a 41 ms token (`130` S0). Every layer stops after its router: the CPU waits for the six selected ids, checks the expert cache, encodes the expert pass and commits it, and only then can the GPU continue. The plan was to take the expert pass off that path by committing it ahead, behind a shared event. Measured on this machine, a CPU-signalled event restarts the GPU no faster than a commit (about 100 us), and the CPU work it would hide is about 10 us per all-hit layer. What can still shrink the idle is work that does not depend on the ids. The shared expert is such work, and today it runs before the readback.

## What Changes

- Commit the router's command buffer on its own, then encode the shared expert into the next one and commit it before waiting. The CPU waits only for the router, so the shared expert runs on the GPU while the CPU reads the ids, checks the cache and encodes the expert pass.
- Same kernels and inputs, so the output stays bitwise; cache bookkeeping is unchanged.
- Rejected, with the measurements in the performance record: the event-gated pre-committed expert pass, a GPU-side spin-wait on shared memory, and an optimistic continuation with rollback.

## Capabilities

### New Capabilities
None. Same results, different submission (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: `ds41_moe_partial` commits the router before the shared expert on a single streaming box. `ds4_metal.m`: `ds4_gpu_split_readback` and the readback wait that commits the split batch and waits only for the earlier ones. `ds4_gpu.h`: one declaration.
- Rollback switch `DS4_METAL_DISABLE_V41_READBACK_SPLIT`, checked by `make test-deepseek41-decode-switch`.
- Builds on `131` (its poll is the wait used at the readback).
- No external SSD.
