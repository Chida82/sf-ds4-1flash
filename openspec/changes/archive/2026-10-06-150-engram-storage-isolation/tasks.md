# Tasks

## 1. Isolation gate and baseline

- [x] 1.1 After the `140` decision, prepare `perf/150-engram-storage-isolation` and the accepted baseline, with dual-SSD up disabled for the first isolation comparison. Verify named baseline Engram/graph tests and which `120`/`140` helpers are actually present.
- [x] 1.2 Read `120`'s exposed Engram cost, then measure only the Engram readiness under internal bulk IO that it does not cover, and identify an approved exact external replica. Verify the report uses production row alignment/workers/conversion and documents exposed contention; stop if the performance gate is shut or if a missing replica would require an unapproved copy.

## 2. Exact secondary-source admission

- [x] 2.1 Add `DS4_ENGRAM_REPLICA` admission and bounded table validation, reusing a landed helper only where applicable. Add tests for default/empty, unsupported modes, same inode, malformed bounds, wrong hash/token-map metadata and altered payload. Verify explicit invalid requests fail before inference and the default inode/range checks are not weakened. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.
- [x] 2.2 Bind session readers to the engine-validated source identity without per-session full rescans. Verify path replacement, observed mutation, cache-generation reset, partial open failure and engine/session teardown tests. Document the option, validation cost and the fact that a complete replica frees no internal space. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.

## 3. Reader and placement correctness

- [x] 3.1 Route existing bounded row reads through the admitted descriptor while retaining conversion, masking, deduplication and async ownership. Run the exhaustive Engram suite and injected EOF/invalid-value/cancel fixtures; verify unchanged error semantics and no whole-table RAM allocation. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.
- [x] 3.2 Compare canonical and isolated source execution on text, image-masked input, continuation and session save/restore. Verify bitwise logits/history and the same admitted expert slots; record which paths were covered. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.

## 4. Placement performance

- [x] 4.1 Review and A/B internal-only versus external Engram (B) and split Engram (D, D4's reader share) with normal `cold,append`, timed decode and both long guards. Verify source/validation logs and the project keep rule; keep at most one placement, fix it as the option's behavior and remove the share diagnostic; remove an additive neutral feature even if it would support a later capacity project. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.
- [x] 4.2 Only if `140` was kept, compare combined external up-plus-Engram against the best accepted placement. Verify contention and row-tail latency are measured rather than gains added; document a losing combination instead of recommending it. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.
- [x] 4.3 Measure engine-open verification and fresh/repeated-request latency, respecting the harness budget and D4's stop rule. Verify the evidence makes initialization cost and break-even explicit, with no cold-start claim based on steady timing alone. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.

## 5. Integration

- [x] 5.1 Review lifecycle/default/failure paths, build Metal and separate CPU binaries, and run named tests plus streaming model/session/eval checks. Verify no split-main format, hole punching, automatic replication or host configuration changes entered scope. Closed by the D1 gate (perf-record, Engram placement after 145): with the `140` copy the sweeps wait 0.00-0.37 s on Engram, and full validation would cost about 30 s per engine open; not implemented.
- [x] 5.2 Complete D4's segment-start/record-row evidence and actual-candidate upstream parity with the secondary source enabled and absent. Verify `openspec validate 150-engram-storage-isolation --strict`, updated measured docs and explicit disposition of closed stages. No commit/push without another request. Done: no runtime change, so no segment row or parity run; the gate and its figures are in perf-record, with a Rejected-ideas row; `openspec validate --strict` passes.
