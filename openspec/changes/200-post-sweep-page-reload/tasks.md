# Tasks

## 1. Gate

- [ ] 1.1 Branch `perf/200-post-sweep-page-reload`, check the Rejected ideas table, and build the probe (D1) in a separate worktree, never landed. Run it on the D1 shapes with and without the copy. Verify: a perf-record section that names which spans are evicted and reloaded, the page-ins per shape, the recoverable time, and a go/stop verdict.

## 2. Fixes

- [ ] 2.1 S1 (D2): background re-warm of the evicted static spans from the sweep's last layers, joined before the sweep returns. Verify: `make test` passes, decode-switch is bitwise with its disable switch, the A/B per D5 has a step row and a verdict, and `vm_stat` shows fewer page-ins after the sweep.
- [ ] 2.2 Only if S1 leaves the reload exposed: S2 (D3). Show the owner the admitted-memory figures before any change to admission, then A/B per D5. Verify: the owner's decision is recorded, then a step row and a verdict, or the recorded reason for not trying it.
- [ ] 2.3 S3 (D4): measure whether the kept state changes the copy's steady decode. Verify: a figure in perf-record with or without the copy, and the cause stated, or recorded as open.

## 3. Final

- [ ] 3.1 Final review, model-backed suites, an A/B against the segment start with its row, parity, and `AGENTS.md`/README updates for any changed first-token figures. Verify: the PASS lines, the row, PARITY OK, and `openspec validate 200-post-sweep-page-reload --strict`. Commit and push remain separately authorized.
