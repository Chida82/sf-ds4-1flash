# Tasks

## 1. Gate

- [x] 1.1 Branch `perf/145-dual-ssd-decode-misses` from the `main` that carries `140`. Check the Rejected ideas table, then build the baseline worktree. Verify: `make test` and `make test-deepseek41-prefill-replica REPLICA=<path>` pass on the baseline.
- [x] 1.2 Run D1 on the baseline with the replica admitted: decode 2048/8192 with `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`, per-family piece latency on each drive with the production pool, the miss-count distribution, and one decode routed pass in `DS4_METAL_ENCODER_TIMELINE`. Record the gate in `speed-bench/perf-record.md`. Stop, recording the figure, if removing a third of the `pread` cannot clear the harness resolution. Verify: the section exists with the figures, and the verdict on D5 is written.

## 2. S4 route-prediction prefetch (first: the gate put S1 at about 0.6%)

- [x] 2.1 Probe (D7) in a separate worktree, never landed. On decode 2048/8192 (256 tokens), log the predicted next-layer top-k with scores, the selected ids and the misses, at both leads. Report recall on misses and wasted reads per token, by score threshold, per-layer cap 1-2, and with and without the hotness filter. Verify: a perf-record section with the table, and a go/stop verdict under the D7 stop rule; on stop, a Rejected-ideas row with the figures.
- [x] 2.2 Implement the minimal D7 variant: layers 20-39, one prefetch per layer through the pending-load slot, settled before the lookup. Add `DS4_METAL_DISABLE_V41_ROUTE_PREFETCH`. A fixture must show that a prefetched expert enters the cache only when selected, and that otherwise its buffers return without an install. Run the decode-switch test with that switch, bitwise. A/B against the kept state, `decode,append` plus guards, `--bitwise`, with cache statistics. Verify: the fixture and decode-switch PASS, then a step row and a keep/drop verdict; the full variant stays in `170`.

## 3. S1 family split (on the kept state, only if exposed `pread` remains measurable)

- [x] 3.1 Pass the admitted replica descriptor and its validated ranges to Metal (D2) and give each `pread` task its descriptor. Route a missing expert's up task to the replica (D3). Extend the Metal streaming and graph fixtures: Done and reverted: implemented (per-task fd on the pread pool, change check), bitwise in `test-deepseek41-prefill-replica`; the fixture was not extended because the step was dropped.
  - up comes from the replica and gate/down from the model, with each file's other ranges clobbered;
  - a short read or an error on the replica fails the step with the slot invalid;
  - a replica changed after validation is refused;
  - without a replica every task reads `g_model_fd`.

  Verify: `make test` and the extended fixture pass.
- [x] 3.2 Extend `test-deepseek41-prefill-replica` to cover decode beyond the prefill frontiers, bitwise and with cache statistics compared. A/B S1 against the kept state with the shared `--env DS4_METAL_PREFILL_REPLICA=<path>`, kinds `decode,append` plus the decode guard, `--bitwise`; repeat an inconclusive run once. Verify: the step row in perf-record has a keep/drop verdict under the project rule. Done: A/B against the S2 state, decode 8192 -1.7% (CI below zero), dropped; Rejected-ideas row added.

## 4. S2 threshold and D5

- [x] 4.1 On the kept state, measure split-deferred thresholds 1, 2 and 3 with the harness (D4). Keep the best as the constant, or keep 3. Verify: step row and verdict recorded; the constant matches the kept winner.
- [x] 4.2 If D1 showed that compute is under the restart cost, add a Rejected-ideas row for compute-before-complete with both figures. Otherwise implement gate/up-first, down-after as its own step and A/B it. Verify: either the row or a step verdict exists.

## 5. S3 wider placement (only if exposed `pread` remains)

- [x] 5.1 Decide from the kept state's timing summary whether the remaining exposed `pread` justifies S3 (D6). If it does, widen `140`'s validation to every routed tensor, and implement byte-proportional and miss-count placement. Measure the startup check and both placements as one step against the kept state, and keep at most one. Verify: the decision is written in perf-record with the figure; if implemented, the step row, the startup time and the break-even count are recorded, and the fixtures cover the new ranges. Done: not tried; S1 showed a single miss is latency-bound on the copy, so wider placement spreads the same misses over the slower device (perf-record).

## 6. Final

- [x] 6.1 Final review of the touched region against `AGENT.md`: delete what the change made dead, and keep output identical. Build Metal and `make cpu`. Run `make test`, command-memory, ssd-experts, deepseek41-metal and `test-deepseek41-prefill-replica`. Verify: every named target prints its PASS lines.
- [x] 6.2 Update `AGENTS.md` and `docs/ssd.md` with the kept placement and its measured gain. A/B against the segment start with the shared replica environment (A ignores it) and append the printed row. Run parity with and without the replica. Verify: the row appended, PARITY OK twice, and `openspec validate 145-dual-ssd-decode-misses --strict` passes. Commit and push remain separately authorized.
