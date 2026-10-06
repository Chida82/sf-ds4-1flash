# Tasks

## 1. Overhead without the drive

- [ ] 1.1 Branch `perf/180-external-ssd-evidence`. Build worktree A: current `main` with `140`'s replica code reverted (D1), diffed against `67b75b8`'s replica-free functions. Verify: `make test` passes in A, and the diff summary is recorded.
- [ ] 1.2 Run the D1 A/B, without the variable, pooled up to three invocations. Verify: a perf-record section with the pooled CIs and an accepted, rejected or inconclusive verdict. If rejected, remove the cost as a step and re-measure.

## 2. With and without the drive

- [ ] 2.1 Run D2's A/B (internal only against the `140` copy) on the current tree. Verify: a perf-record section with the figures.
- [ ] 2.2 Add the README table with the hardware, conditions and links, and quote `160`'s KV cache cost. Verify: the README in English, the numbers matching the record, and `openspec validate 180-external-ssd-evidence --strict` passing. Commit and push remain separately authorized.
