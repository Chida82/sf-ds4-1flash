# Tasks

## 1. Stamp

- [ ] 1.1 In `ds41_prefill_replica_open`, read the attribute before the comparison and skip it when every field of D1 matches; write it after a pass (D3); remove it after a failure; honour `DS4_METAL_PREFILL_REPLICA_FULL_CHECK=1`; print which path ran. Verify `make` and `make test`.
- [ ] 1.2 Extend `make test-deepseek41-prefill-replica` with the D5 cases (write, skip, `touch`, truncated copy, forced check). Verify the target names each case as it passes.

## 2. Evidence and documentation

- [ ] 2.1 Time two consecutive CLI opens with the copy on `/Volumes/ExtSSD`, before and after; record the figures in `speed-bench/perf-record.md`. Update the replica paragraph in `AGENTS.md` and the README's second-drive section (the 7 s figure, the stamp, how to force the full check). Verify `openspec validate 280-replica-check-stamp --strict`. No commit or push without a request.
