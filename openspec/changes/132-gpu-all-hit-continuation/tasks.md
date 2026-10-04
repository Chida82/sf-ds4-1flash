# Tasks

## 1. Gate

- [ ] 1.1 After `130`/`131`, prepare `perf/132-gpu-all-hit-continuation` and its baseline; re-measure per-layer wake, CPU and commit-to-start components and the all-hit layer share for decode, append and a long answer. Verify the performance record states them; close the change if encode plus queue is under 50 us per layer.

## 2. Event-gated expert pass

- [ ] 2.1 Implement D2/D3 with a rollback switch: B committed behind a shared-event wait, ids from the router's GPU buffer, address-table slots written and protected before the CPU signal, every error and cancel path signalling. Verify the forced-miss, delayed-signal, load-error and cancellation fixtures pass bitwise against the old path.
- [ ] 2.2 Run `make test-deepseek41-decode-switch` with the switch, graph queue parity and streaming-cache tests; check `--cache-stats` counters equal. Verify all pass.
- [ ] 2.3 A/B `decode,append` with long and cold guards, `--bitwise`, against the previous kept tree. Verify the keep rule (including the 800-line threshold), record the row and the gap components after, and remove the code if not kept.

## 3. Integration

- [ ] 3.1 Review the touched region, build `make` and separate `make cpu`, run the named suite, model-backed session checks, the segment-start A/B and candidate parity. Verify `openspec validate 132-gpu-all-hit-continuation --strict`. No commit or push without a request.
