# Tasks

## 1. Overhead without the drive

- [x] 1.1 Branch `perf/180-external-ssd-evidence`. Build worktree A: current `main` with `140`'s replica code reverted (D1), diffed against `67b75b8`'s replica-free functions. Verify: `make test` passes in A, and the diff summary is recorded.
- [x] 1.2 Run the D1 A/B, without the variable, pooled up to three invocations. Verify: a perf-record section with the pooled CIs and an accepted, rejected or inconclusive verdict. If rejected, remove the cost as a step and re-measure. Done: three invocations, 114 pairs, inconclusive under D1 (no CI wholly below -0.1%, several lower bounds below it, prefill B faster); the owner accepted it on 2026-10-06.

## 2. With and without the drive

- [x] 2.1 Run D2's A/B (internal only against the `140` copy) on the current tree. Verify: a perf-record section with the figures. Done: two invocations pooled (perf-record, External SSD evidence after 170).
- [x] 2.2 Add the README table with the hardware, conditions and links, and quote `160`'s KV cache cost. Verify: the README in English, the numbers matching the record, and `openspec validate 180-external-ssd-evidence --strict` passing. Commit and push remain separately authorized. Done: README table in "A second drive", 160's KV cache cost quoted above it.
