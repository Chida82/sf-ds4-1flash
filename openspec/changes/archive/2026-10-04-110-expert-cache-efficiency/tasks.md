# Tasks

## 1. Current cache evidence

- [x] 1.1 After `100` is resolved, prepare `perf/110-expert-cache-efficiency` and a baseline; verify named baseline cache/graph tests and the fixed admitted capacity, including any RAM-copy protection now present. (Branch at `896785c`; `make test` 22 PASS, `test-metal-ssd-experts` and `test-deepseek41-metal` green; 82GB -> 74.88 GiB, 8078 slots; `100` added no cache-entry protection, its RAM copy waits before any seed.)
- [x] 1.2 Collect scan/clear/bind counters and new 40-layer routing traces for short/long decode and appends. Replay with `expert_cache_sim.py`, verify its self-test and document empty-cache/protection differences in the performance record. Close any stage without recoverable cost. (Timing summary, traces and a re-miss probe for decode, append and a 2500-token answer; simulator self-test ok; record section "Expert cache after 100" with the empty-cache and seed differences. D2 ceiling under 1%; D3 bounded by re-misses.)

## 2. Live index without a policy change

- [x] 2.1 Review #621 `61e35e2` and implement only the applicable live-entry index. Add old-scan comparison and index-bijection cases to the existing streaming tests; verify stable tie victims through install/clear/reuse/seed/reset and injected errors. (Closed at the D1 gate: a scan is 0.05 ms, at most 0.7% of a short-answer token; `61e35e2` changes 722 lines and would need +1.5%. Not implemented.)
- [x] 2.2 Exercise in-flight/protected and batch-victim cases with `make test-metal-ssd-experts` and graph queue tests. Review and time normal `decode,append` A/B; verify unchanged cache counts, bitwise output and a passing keep gate. Record the exact upstream verdict and remove a neutral index. (Not run: 2.1 closed; verdict `history` recorded for `61e35e2`, no index to remove.)

## 3. Independent LRU trial

- [x] 3.1 If fresh traces justify it, implement D3's oldest-eligible comparator using the previous kept structures. Verify selected/in-flight entries remain protected, preload/seeding admission stays unchanged, and adversarial streams cannot recycle live GPU data. (Trial as a hotness-held-at-zero switch, so every comparator falls to `last_used` with the same protection, in-flight and seeding rules; removed after measuring.)
- [x] 3.2 Measure with `--cache-policy-change`, bitwise output, cold and long guards; report hits, misses and bytes for both builds. Verify the project gate rather than a replay-only advantage, document the winner, and remove losing policy switches and any genuinely dead hotness work. (Deterministic miss counts: LRU decode 13977 vs 13892, append 16016 vs 15979, long answer 9985 equal; never fewer misses, so no harness run. Old policy kept, switch removed, hotness work unchanged.)

## 4. Integration

- [x] 4.1 Review lifecycle/refcount/count invariants across all callers, build Metal and separate CPU binaries, and run named model-less/Metal/session tests plus streaming eval. Verify all #1125 safety cases still pass and capacity never changes between A/B. (No runtime code remains: `ds4.c`, `ds4_metal.m`, `metal/` and the tests equal `main`. `make` and `make cpu` without warnings, named tests green; #1125 cases in `test-metal-ssd-experts` pass; capacity fixed at 8078 slots.)
- [x] 4.2 Run the segment-start comparison and actual-candidate upstream parity, append the final performance row and update acted-on registry entries. Verify `openspec validate 110-expert-cache-efficiency --strict` and clean scope; commits/pushes require a separate request. (No runtime change, so no segment row and no parity run, as for `80` and `90`; record, rejected-ideas rows and the #621/`61e35e2` registry lines updated.)
