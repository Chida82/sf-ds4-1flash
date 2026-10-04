# Proposal

## Why

In streaming decode the GPU idles about 12 ms of a 41 ms token (`130` S0). Every layer stops after its router: the CPU waits for the six selected ids, checks the expert cache, encodes the expert pass and commits it, and only then can the GPU continue. Of the about 295 us this costs per layer, 115 us are CPU work and 103 us are the trip from commit to GPU start; in steady decode all six experts are already cached in 90-98% of layers, so for most layers the CPU decides nothing. Taking the expert pass off that path is the largest remaining decode lever on this machine.

## What Changes

- Encode and commit each layer's expert pass before its ids are known. The pass reads the selected ids from the router's GPU buffer and the expert addresses from the layer's existing address table, and it starts only when the CPU signals a shared event.
- The CPU still reads the ids after the router, checks the cache and, on a miss, loads the expert and writes its address-table slot before signalling. All-hit layers signal after the check alone. Output stays bitwise: the GPU never reads an address the CPU has not validated for this token.
- Cache bookkeeping (hits, recency, hotness, protection, in-flight state) keeps happening on the CPU at the same point in the token, so the cache policy and counters are unchanged.
- An optimistic variant (the GPU runs ahead and the token is rolled back on a miss) is recorded as rejected: a whole token is all-hit in only 1.5% (short answers) to 39% (long answers) of tokens, so rollbacks would dominate.

## Capabilities

### New Capabilities
None. Same results, different submission (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: the streaming routed MoE readback boundary, the address-table kernels' id source, a shared event per command stream; `ds4.c` only where the decode loop commits.
- Tests: graph queue and streaming-cache tests, a fixture that forces misses, delayed signals and errors; `make test-deepseek41-decode-switch`.
- Builds on `131` if kept (its wait primitive), but does not need it.
- No external SSD.
