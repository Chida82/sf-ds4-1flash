# Tasks

## 1. Attribution after the accepted kernel work

- [x] 1.1 Resolve changes through `120`, prepare `perf/130-m5-decode-submission` and the baseline, and run named baseline command/cache/graph tests. Verify actual post-70 dispatch and flush boundaries rather than applying an old PR mechanically. (Branch at `bfa0ef2`; `make test-metal-command-memory` and the named suite green. Post-`70` boundaries: A committed and waited for the selected ids, B flushed at layer end, the next A committed while B runs.)
- [x] 1.2 Capture CPU lookup/encoding costs and GPU gaps for D1's shapes with existing tools, then an uninstrumented A/A. Verify the performance record excludes GPU computation inside `sync` from the removable budget; close the change if neither local step is actionable. (GPU busy against wall over 256 decoded tokens, `CB_TIMES`, a wake/commit probe and `sample`; record section "Decode submission after 120". GPU idle 11-12 ms per token, 310 us per layer in front of B: 76 wake, 115 CPU, 103 commit-to-start; lookups about 1% of wall. D2 open, D3 closed.)

## 2. Allocation-free hot lookup

- [x] 2.1 Review #1067 `d1738d2`, reuse existing fast lookup/hot pointers for measured getters, and add function-constant/negative-cache/reset comparisons. Verify initialization remains on the safe owner thread and existing pipeline test hooks pass. (Plain getter on the existing fast cache with a sentinel nsg, armed for each V4.1 decode step and restored after logits; `DS4_METAL_DISABLE_V41_DECODE_PIPELINE_FAST_LOOKUP` rolls it back. Decode inserts 21 pipelines in 64 slots; the cache is reset by the existing cleanup, compilation stays on the encoding thread.)
- [x] 2.2 Review and A/B normal `decode,append` with cold/long guards and bitwise logits; document key/lifetime behavior and update the commit's verdict. Verify the independent project gate; remove an additive neutral path. (Two invocations pooled, 22 pairs, bitwise, hit rates equal: decode 2048 +0.42% (+0.28..+0.63), 8192 +0.23% (+0.02..+0.67), no metric below zero; kept. `d1738d2` recorded as adopt.)

## 3. Conditional encoding coalescing

- [x] 3.1 If measurable gaps remain, coalesce only D3's adjacent safe region, preserving readback, blit, hazard, completion and cancellation boundaries. Add delayed-completion/error/reset cases; verify command-memory, streaming-cache and graph queue parity tests. (Closed: the gap after B is 1 us; the only gap is the selected-id readback, which no coalescing can cross. Not implemented.)
- [x] 3.2 Review and measure against the previous kept tree, record the safe region and outcome, and remove the trial on regressions or no gain. Verify TP/layer-slice behavior and `30`'s accepted flush schedule were not changed. (Not run: 3.1 closed. TP, layer-slice and `30`'s flush schedule untouched.)

## 4. Integration and explicit scope stop

- [x] 4.1 Review the whole touched region, build `make` and separate `make cpu`, run the named suite and streaming model/session/eval checks. Verify no global hazard disable, MTL4 migration, GPU miss scheduler or CPU/ANE inference path was introduced. (`make` and `make cpu` without warnings, `-cpu*` binaries separate; `make test`, `test-metal-command-memory`, `test-metal-ssd-experts`, `test-deepseek41-metal` green; `ds4_test` streaming session-snapshot, long-context, streaming-decode-prefill and tensor-equivalence ok; `eval --suite hard-smoke` ran end to end, 9 passed and 3 at the token cap, unchanged by construction since the step is bitwise. No hazard disable, MTL4, GPU miss scheduler or CPU/ANE path.)
- [x] 4.2 Record any remaining gaps as evidence for D4's deferred alternatives, then complete segment-start A/B and candidate-verified upstream parity. Verify the printed row and `openspec validate 130-m5-decode-submission --strict`; no implementation expansion, commit or push without another request. (Remaining gaps recorded as evidence for `131` and `132`, written as separate changes. Segment row 12 + 33 pairs, PASS bitwise; parity OK on the candidate, 10 prompts.)
