# Tasks

## 1. Attribution after the accepted kernel work

- [ ] 1.1 Resolve changes through `120`, prepare `perf/130-m5-decode-submission` and the baseline, and run named baseline command/cache/graph tests. Verify actual post-70 dispatch and flush boundaries rather than applying an old PR mechanically.
- [ ] 1.2 Capture CPU lookup/encoding costs and GPU gaps for D1's shapes with existing tools, then an uninstrumented A/A. Verify the performance record excludes GPU computation inside `sync` from the removable budget; close the change if neither local step is actionable.

## 2. Allocation-free hot lookup

- [ ] 2.1 Review #1067 `d1738d2`, reuse existing fast lookup/hot pointers for measured getters, and add function-constant/negative-cache/reset comparisons. Verify initialization remains on the safe owner thread and existing pipeline test hooks pass.
- [ ] 2.2 Review and A/B normal `decode,append` with cold/long guards and bitwise logits; document key/lifetime behavior and update the commit's verdict. Verify the independent project gate; remove an additive neutral path.

## 3. Conditional encoding coalescing

- [ ] 3.1 If measurable gaps remain, coalesce only D3's adjacent safe region, preserving readback, blit, hazard, completion and cancellation boundaries. Add delayed-completion/error/reset cases; verify command-memory, streaming-cache and graph queue parity tests.
- [ ] 3.2 Review and measure against the previous kept tree, record the safe region and outcome, and remove the trial on regressions or no gain. Verify TP/layer-slice behavior and `30`'s accepted flush schedule were not changed.

## 4. Integration and explicit scope stop

- [ ] 4.1 Review the whole touched region, build `make` and separate `make cpu`, run the named suite and streaming model/session/eval checks. Verify no global hazard disable, MTL4 migration, GPU miss scheduler or CPU/ANE inference path was introduced.
- [ ] 4.2 Record any remaining gaps as evidence for D4's deferred alternatives, then complete segment-start A/B and candidate-verified upstream parity. Verify the printed row and `openspec validate 130-m5-decode-submission --strict`; no implementation expansion, commit or push without another request.
