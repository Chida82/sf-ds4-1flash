# Tasks

## 1. Gate

- [ ] 1.1 After `130`, prepare `perf/131-decode-readback-spin-wait` and its baseline; re-measure the per-layer wake, CPU and queue components with `130`'s probe method. Verify the performance record states the wake figure; close the change if it is under 20 us per layer.

## 2. Bounded poll

- [ ] 2.1 Implement D2 at the streaming decode readback with a rollback switch, comparing the status and shared-event primitives in a micro-probe and keeping one. Verify `make test-deepseek41-decode-switch` passes with the switch, the command-memory and streaming-cache tests pass, and the probe reports how often the bound is reached.
- [ ] 2.2 A/B `decode,append` with long and cold guards, `--bitwise`, against the previous kept tree. Verify the keep rule, record the row and the wake figure before and after, and remove the poll if it is neutral or slower.

## 3. Integration

- [ ] 3.1 Review the touched region, build `make` and separate `make cpu`, run the named suite, the segment-start A/B and candidate parity. Verify `openspec validate 131-decode-readback-spin-wait --strict`. No commit or push without a request.
