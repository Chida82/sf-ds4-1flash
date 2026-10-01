# Tasks

## 1. Current cache evidence

- [ ] 1.1 After `100` is resolved, prepare `perf/110-expert-cache-efficiency` and a baseline; verify named baseline cache/graph tests and the fixed admitted capacity, including any RAM-copy protection now present.
- [ ] 1.2 Collect scan/clear/bind counters and new 40-layer routing traces for short/long decode and appends. Replay with `expert_cache_sim.py`, verify its self-test and document empty-cache/protection differences in the performance record. Close any stage without recoverable cost.

## 2. Live index without a policy change

- [ ] 2.1 Review #621 `61e35e2` and implement only the applicable live-entry index. Add old-scan comparison and index-bijection cases to the existing streaming tests; verify stable tie victims through install/clear/reuse/seed/reset and injected errors.
- [ ] 2.2 Exercise in-flight/protected and batch-victim cases with `make test-metal-ssd-experts` and graph queue tests. Review and time normal `decode,append` A/B; verify unchanged cache counts, bitwise output and a passing keep gate. Record the exact upstream verdict and remove a neutral index.

## 3. Independent LRU trial

- [ ] 3.1 If fresh traces justify it, implement D3's oldest-eligible comparator using the previous kept structures. Verify selected/in-flight entries remain protected, preload/seeding admission stays unchanged, and adversarial streams cannot recycle live GPU data.
- [ ] 3.2 Measure with `--cache-policy-change`, bitwise output, cold and long guards; report hits, misses and bytes for both builds. Verify the project gate rather than a replay-only advantage, document the winner, and remove losing policy switches and any genuinely dead hotness work.

## 4. Integration

- [ ] 4.1 Review lifecycle/refcount/count invariants across all callers, build Metal and separate CPU binaries, and run named model-less/Metal/session tests plus streaming eval. Verify all #1125 safety cases still pass and capacity never changes between A/B.
- [ ] 4.2 Run the segment-start comparison and actual-candidate upstream parity, append the final performance row and update acted-on registry entries. Verify `openspec validate 110-expert-cache-efficiency --strict` and clean scope; commits/pushes require a separate request.
