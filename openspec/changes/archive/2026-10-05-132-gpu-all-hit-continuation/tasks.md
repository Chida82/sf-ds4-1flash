# Tasks

## 1. Gate

- [x] 1.1 After `130`/`131`, prepare `perf/132-gpu-all-hit-continuation` and its baseline; re-measure per-layer wake, CPU and commit-to-start components and the all-hit layer share in decode, and the CPU-signalled event restart latency. Verify the performance record states them; close the event-gated pass if its saving (CPU encode) is under 50 us per layer.

## 2. Readback split

- [x] 2.1 Implement D2 with the rollback switch: the router committed alone, the shared expert in the next batch, the readback waiting only for the earlier batches, cache sequences and transient buffers carried. Verify `make test-deepseek41-decode-switch` passes bitwise with the switch.
- [x] 2.2 Run the graph queue parity and streaming-cache tests; check the hit rates equal in the harness. Verify all pass.
- [x] 2.3 A/B `decode,append` with long and cold guards, `--bitwise`, against the previous kept tree. Verify the keep rule, record the row and the gap components after, and remove the code if not kept.

## 3. Integration

- [x] 3.1 Review the touched region, build `make` and separate `make cpu`, run the named suite, model-backed session checks, the segment-start A/B and candidate parity. Verify `openspec validate 132-gpu-all-hit-continuation --strict`. No commit or push without a request.
