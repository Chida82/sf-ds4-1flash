# Tasks

## 1. Post-70 baseline and gate

- [ ] 1.1 Confirm `60`/`70` are resolved, create `perf/80-m5-decode-kernels` and a baseline worktree without altering existing dirty work. Verify branch identities, rerere, model link and the baseline's named `make test` output; record pre-existing failures separately.
- [ ] 1.2 Capture D1's kernel names/times, CPU gaps and reads at 2K/8K plus the 32K diagnostic; run uninstrumented A/A. Verify `speed-bench/perf-record.md` records the gate and current noise, not the historical wait counter as recoverable overhead. Stop here if neither target is actionable and record why later tasks do not apply.

## 2. Dense output-row locality

- [ ] 2.1 Extend the existing Metal fixture with original-versus-candidate Q8 comparisons for the live post-70 shapes, offsets, odd row tails and edge values. Verify tests fail for an intentionally wrong row mapping in a disposable scratch build and pass on the original path.
- [ ] 2.2 Trial D2's bounded row groupings without changing K/NSG/rounding; keep unsupported shapes on the original dispatch. Verify raw output bytes and `make test-deepseek41-metal`; check any new Makefile rule by dry-run output, not exit code alone.
- [ ] 2.3 Review and A/B the dense step with `--bitwise`, `decode,append` and D4's guards. Verify pooled target/no-regression evidence under the project gate, record the decision with run paths and supported shapes, and remove losing candidates before proceeding.

## 3. Independent indexer locality

- [ ] 3.1 If its own gate passed, add a bounded multi-row scorer preserving the old per-row head/dot order. Verify byte-identical scores and selected IDs/order on tied/all-zero and irregular-row cases in `tests/test_deepseek41_metal.c`.
- [ ] 3.2 Review and measure against the previous kept tree with the same correctness and throughput gate; document the result and any #1061/#959 action without reviving rejected reductions. Verify no unmeasured additive path remains.

## 4. Integration and evidence

- [ ] 4.1 Review all touched callers, remove dead trial code, build `make` and separate `make cpu`, and run the named model-less/Metal tests plus model-backed session/eval checks with SSD streaming. Verify default Metal binaries were not overwritten and TP/vision fallbacks remain intact; ask separately before distributed model runs.
- [ ] 4.2 Compare the final tree to the current performance segment start, append its printed record row, and run the upstream parity oracle with `SF_PARITY_FLAGS=--ssd-streaming`. Verify it actually targets this candidate rather than the registry's sibling checkout; stop if it does not, or if correctness/parity fails.
- [ ] 4.3 Check scope and `openspec validate 80-m5-decode-kernels --strict`. Verify all kept steps have recorded evidence and any skipped stage has an explicit disposition. Do not commit or push without a new request.
