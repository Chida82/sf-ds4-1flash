# Tasks

## 1. Stamp

- [x] 1.1 In `ds41_prefill_replica_open`, read the attribute before the comparison and skip it when every field of D1 matches; write it after a pass (D3); remove it after a failure; honour `DS4_METAL_PREFILL_REPLICA_FULL_CHECK=1`; print which path ran. Verify `make` and `make test`.
  - Done 2026-10-10. `make` has no warnings, and `make test` passes.
- [x] 1.2 Extend `make test-deepseek41-prefill-replica` with the D5 cases (write, skip, `touch`, truncated copy, forced check). Verify the target names each case as it passes.
  - Done 2026-10-10. `make test` prints each stamp case PASS: second open skipped, forced check refused a changed copy, new mtime restamped, truncated copy refused.

## 2. Evidence and documentation

- [x] 2.1 Time two consecutive CLI opens with the copy on `/Volumes/<drive>`, before and after; record the figures in `speed-bench/perf-record.md`. Update the replica paragraph in `AGENTS.md` and the README's second-drive section (the 7 s figure, the stamp, how to force the full check). Verify `openspec validate 265-replica-check-stamp --strict`. No commit or push without a request.
  - Done 2026-10-10 with the copy on APFS. `main` opened in 13.07 and 10.86 s, comparing each time in 6.7 s. `265` opened in 10.88 s (compared, stamped), then 4.14 s (skipped). `perf-record.md` has the section; `AGENTS.md` and the README describe the stamp and the forced check.
