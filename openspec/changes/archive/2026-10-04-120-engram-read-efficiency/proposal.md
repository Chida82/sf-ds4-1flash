# Proposal

## Why

Engram reads only 48 small rows per text token but performs random I/O, sorting and scalar E4M3/E8M0 conversion; `70` may already hide much of that latency. After `110`, optimize only the exposed remainder, using the actual Engram path rather than the thread-startup-dominated batch timings in the storage microbenchmark.

## What Changes

- Measure decode readiness and prefill conversion/read costs after the kept `70` asynchronous work.
- Replace expensive scalar conversion only with a bit-exact lookup/bit-manipulation or NEON implementation, checked against the existing exhaustive scaled-value oracle.
- Independently improve deduplication across reader partition boundaries, then evaluate a small bounded raw-row cache only when measured row reuse justifies it.
- Independently assess replacing the full-prefix prefetch output with bounded tile buffering if its lifetime wastes meaningful memory; no change to the numerical prefill schedule.
- Keep hashing, image masking, row order, validation and error behavior unchanged. No external storage here; `150` owns that alternative.

## Capabilities

### New Capabilities
None. Internal implementation with identical observable results (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_engram.c/.h`, Engram prefetch ownership in `ds4.c`, `tests/test_engram.c`, graph prefetch/cancellation tests and performance documentation.
- Reuse 16-reader GCD batching and the existing 256 x 256 scaled-value test; do not add a second thread framework or change compiler floating-point flags.
- #1035 is already superseded and #1117 is Linux-only. Neither justifies another reader-pool port.
