# Design

## Context

See proposal.md. Victim selection currently ranks eligible entries by hotness then last_used, with iteration order resolving remaining ties. The arrays allow 80 x 384 entries, but scans skip empty layers: do not repeat the registry's maximum-capacity count as a measured scan count. #1125 established entry-count, slot-return and in-flight safety. `100` may add short-lived protection for RAM-source copies.

## Goals / Non-Goals

**Goals:** reduce host management cost and, separately, miss cost at fixed capacity.

**Non-Goals:** larger cache, approximate experts, route prediction, replacing the pread pool, or a collection of permanent eviction algorithms.

## Decisions

### D1. Fresh evidence after weight delivery

After `100` is resolved, collect scan entries/time, clear time, hits/misses and read bytes at decode 2048/8192, append +300/+1500 and a long answer. Use the existing trace recorder and simulator. The simulator starts empty and models individual accesses, not prefill seeds or in-flight reservations; use its LRU/Belady numbers only as bounds, not a prediction of production misses. A measured no-op result closes a step.

### D2. Live-entry index, same comparator

Evaluate #621 `61e35e2` as a source, not a ready-made V4.1 patch. Maintain a bounded index through install, clear, reuse, seeding, rollback and full reset; enforce a bijection with valid entries. The index is owned by the same thread/synchronization as the current cache. Eligibility keeps in-flight and explicit protection checks, including any kept `100` protection.

Index iteration order must not change equal-key victims: compare the original layer/expert traversal position as the final tie-break. Both single- and batch-victim scans must choose the same victim sequence as the old scan. A compact unsorted live list with explicit tie ordering is preferred over a heap requiring continuous hotness updates.

### D3. LRU as an independent measured policy trial

Only when new traces show recoverable miss cost, trial choosing the oldest eligible last_used entry globally. Reuse existing timestamps; preserve admission, same-step selected protection, GPU-copy completion and failure cleanup. Do not treat in-flight data as evictable because a replay did. Leave seeding/admission unchanged for this trial. If LRU fails on TTFT, short decode or the long-answer guard, keep the old policy even if a selected trace looks better.

D2 does not have to land to test D3: LRU can use the existing full scan. A neutral live index cannot be kept as a prerequisite. If a policy wins, remove obsolete hotness work only after checking every preload/seeding consumer.

### D4. Correctness and measurement

Model-less fixtures compare victim sequences, equal-key cases, batch victims, count invariants, allocation/read failure rollback and protection release. `make test-metal-ssd-experts` must name and run its formats; graph queue/session tests stress reuse while GPU work is pending. All model-backed outputs/logits must stay bitwise.

D2 uses ordinary cache-state pairing and should reproduce counts. D3 uses `--cache-policy-change` and reports the changed hit rate/bytes rather than hiding them. Timed targets are `decode,append`; cold prompts and both long guards protect seeding and drift. Enforce the project per-step CI/size rule, repeat an inconclusive decision once, and reject additive neutral code. Finish with the segment-start comparison and actual-candidate upstream parity.

## Risks / Trade-offs

- One forgotten clear path leaves stale live entries -> enumerate all install/clear/error/reset callers and test their invariants.
- New traversal changes tie victims -> old-scan oracle, explicit stable tie-break.
- LRU helps one prose trace but thrashes another -> multiple existing parity prompts plus long answer, not only the simulator.
- Policy changes disturb subsequent experiments -> finalize the winner before `120`; keep the measured slot count fixed.

## Migration Plan

Branch `perf/110-expert-cache-efficiency` after earlier decisions. No persistent cache format or CLI mode. Update acted-on PR lines and measured outcomes; remove rejected switches/structures. Review and build both Metal and separate CPU targets before a separately authorized landing.
