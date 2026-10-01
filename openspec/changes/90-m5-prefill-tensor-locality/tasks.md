# Tasks

## 1. Baseline and section gate

- [ ] 1.1 After `80` is resolved, prepare `perf/90-m5-prefill-tensor-locality` and its baseline, preserving all unrelated work. Verify `60`'s final LUT/kernel choices, named baseline tests and the actual packed-path dispatches.
- [ ] 1.2 Run D1's section/A/A probes on cold/append shapes using installed tools only. Verify the performance record states which staging/locality cost is actionable; close the change without kernels if its gate is shut.

## 2. Expert-local traversal

- [ ] 2.1 Implement D2's mapping and its coverage oracle in the existing MoE fixture. Verify irregular grids, empty experts, partial tiles and TP ownership cover each legal tile exactly once; keep the old matmul descriptor/K loop.
- [ ] 2.2 Run `make test-metal-moe-prefill`, compare intermediate bytes and frontier logits, then review and measure the step under D5. Verify its own keep verdict, record shape gates/results and delete it if neutral or regressing.

## 3. Cooperative-input staging

- [ ] 3.1 Add the exact dequantized-half cooperative-input path with compile/runtime fallback, without changing accumulation. Verify exhaustive dequant cases, packed threshold/tail fixtures and bitwise intermediates; stop this stage if API compatibility requires different arithmetic.
- [ ] 3.2 Review and compare to the previous kept path with per-shape section evidence and a normal harness guard. Verify the recorded keep/drop decision includes register/occupancy evidence when available and that no rejected variant remains.

## 4. Conditional paired epilogue

- [ ] 4.1 Only if D4's headroom gate passes, implement independent gate/up accumulators and the unchanged clamp/SwiGLU/weight/cast sequence. Verify boundary-value and partial-tile tests reproduce gate/up/mid/down bytes.
- [ ] 4.2 Measure this step independently, document the arithmetic boundary and decision, and remove it on bit drift or no benefit. Verify it does not require keeping a neutral prior stage.

## 5. Integration

- [ ] 5.1 Review the complete touched region, build Metal and separate CPU targets, run the named model-less and Metal suites, and execute normal `cold,append`, timed decode and both long guards. Verify the normal throughput/e2e gates and bitwise output, not just section ratios.
- [ ] 5.2 Run the segment-start comparison and actual-candidate upstream parity with SSD streaming; append the record row and update only acted-on PR verdicts. Verify `openspec validate 90-m5-prefill-tensor-locality --strict` and the final scope; commit/push requires a separate request.
