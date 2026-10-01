# Tasks

## 1. Isolation gate and baseline

- [ ] 1.1 After the `140` decision, prepare `perf/150-engram-storage-isolation` and the accepted baseline, with dual-SSD up disabled for the first isolation comparison. Verify named baseline Engram/graph tests and which `120`/`140` helpers are actually present.
- [ ] 1.2 Measure actual Engram readiness under internal bulk IO and identify an approved exact external replica. Verify the report uses production row alignment/workers/conversion and documents exposed contention; stop if the performance gate is shut or if a missing replica would require an unapproved copy.

## 2. Exact secondary-source admission

- [ ] 2.1 Add `DS4_ENGRAM_REPLICA` admission and bounded table validation, reusing a landed helper only where applicable. Add tests for default/empty, unsupported modes, same inode, malformed bounds, wrong hash/token-map metadata and altered payload. Verify explicit invalid requests fail before inference and the default inode/range checks are not weakened.
- [ ] 2.2 Bind session readers to the engine-validated source identity without per-session full rescans. Verify path replacement, observed mutation, cache-generation reset, partial open failure and engine/session teardown tests. Document the option, validation cost and the fact that a complete replica frees no internal space.

## 3. Reader and placement correctness

- [ ] 3.1 Route existing bounded row reads through the admitted descriptor while retaining conversion, masking, deduplication and async ownership. Run the exhaustive Engram suite and injected EOF/invalid-value/cancel fixtures; verify unchanged error semantics and no whole-table RAM allocation.
- [ ] 3.2 Compare canonical and isolated source execution on text, image-masked input, continuation and session save/restore. Verify bitwise logits/history and the same admitted expert slots; record which paths were covered.

## 4. Placement performance

- [ ] 4.1 Review and A/B internal-only versus external Engram with normal `cold,append`, timed decode and both long guards. Verify source/validation logs and the project keep rule; remove an additive neutral feature even if it would support a later capacity project.
- [ ] 4.2 Only if `140` was kept, compare combined external up-plus-Engram against the best accepted placement. Verify contention and row-tail latency are measured rather than gains added; document a losing combination instead of recommending it.
- [ ] 4.3 Measure engine-open verification and fresh/repeated-request latency, respecting the harness budget and D4's stop rule. Verify the evidence makes initialization cost and break-even explicit, with no cold-start claim based on steady timing alone.

## 5. Integration

- [ ] 5.1 Review lifecycle/default/failure paths, build Metal and separate CPU binaries, and run named tests plus streaming model/session/eval checks. Verify no split-main format, hole punching, automatic replication or host configuration changes entered scope.
- [ ] 5.2 Complete D4's segment-start/record-row evidence and actual-candidate upstream parity with the secondary source enabled and absent. Verify `openspec validate 150-engram-storage-isolation --strict`, updated measured docs and explicit disposition of closed stages. No commit/push without another request.
