# Tasks

## 1. Post-70 baseline and gate

- [x] 1.1 Confirm `60`/`70` are resolved, create `perf/80-m5-decode-kernels` and a baseline worktree without altering existing dirty work. Verify branch identities, rerere, model link and the baseline's named `make test` output; record pre-existing failures separately.
- [x] 1.2 Capture D1's kernel names/times, CPU gaps and reads at 2K/8K plus the 32K diagnostic; run uninstrumented A/A. Verify `speed-bench/perf-record.md` records the gate and current noise, not the historical wait counter as recoverable overhead. Stop here if neither target is actionable and record why later tasks do not apply.

## 2. Dense output-row locality

- [x] 2.1 Extend the existing Metal fixture with original-versus-candidate Q8 comparisons for the live post-70 shapes, offsets, odd row tails and edge values. Verify tests fail for an intentionally wrong row mapping in a disposable scratch build and pass on the original path.
- [x] 2.2 (Trial: the five families as templates over 1/2/4 rows, RoPE 2/4, chosen by a diagnostic `DS4_METAL_V41_Q8_NR0`; `--q8-rows` bitwise for every grouping, `make test-deepseek41-metal` green; no Makefile rule added.) Trial D2's bounded row groupings without changing K/NSG/rounding; keep unsupported shapes on the original dispatch. Verify raw output bytes and `make test-deepseek41-metal`; check any new Makefile rule by dry-run output, not exit code alone.
- [x] 2.3 (Dropped: pooled over `80-s1.1` and `80-s1b.2`, decode 2048 -0.57% (-1.00..-0.10), decode 8192 +0.14% (-0.24..+0.51); trial code, switch and fixture reverted to `main`; recorded in `speed-bench/perf-record.md`.) Review and A/B the dense step with `--bitwise`, `decode,append` and D4's guards. Verify pooled target/no-regression evidence under the project gate, record the decision with run paths and supported shapes, and remove losing candidates before proceeding.

## 3. Independent indexer locality

- [x] 3.1 (Not run: the indexer gate closed in 1.2, 0.18/0.45 ms per token at 2K/8K.) If its own gate passed, add a bounded multi-row scorer preserving the old per-row head/dot order. Verify byte-identical scores and selected IDs/order on tied/all-zero and irregular-row cases in `tests/test_deepseek41_metal.c`.
- [x] 3.2 (Not run, gate closed; #1061's registry line carries the measured scorer cost, #959 unchanged, no reduction revived.) Review and measure against the previous kept tree with the same correctness and throughput gate; document the result and any #1061/#959 action without reviving rejected reductions. Verify no unmeasured additive path remains.

## 4. Integration and evidence

- [x] 4.1 (No runtime code remains: `ds4_metal.m`, `metal/` and the tests equal `main`. `make` and `make cpu` build without warnings, the CPU binaries are `-cpu*`, `make test` rc 0 naming its tests, `make test-deepseek41-metal` green; model-backed and distributed checks have nothing new to check.) Review all touched callers, remove dead trial code, build `make` and separate `make cpu`, and run the named model-less/Metal tests plus model-backed session/eval checks with SSD streaming. Verify default Metal binaries were not overwritten and TP/vision fallbacks remain intact; ask separately before distributed model runs.
- [x] 4.2 (Not run: the candidate's runtime is `main` at `6da9533`, whose `70` row and parity stand; no row appended.) Compare the final tree to the current performance segment start, append its printed record row, and run the upstream parity oracle with `SF_PARITY_FLAGS=--ssd-streaming`. Verify it actually targets this candidate rather than the registry's sibling checkout; stop if it does not, or if correctness/parity fails.
- [x] 4.3 (Scope: `speed-bench/perf-record.md`, `docs/upstream-prs.md`, this change; the `.claude/` files are the separate OpenSpec 1.14.0 refresh. `--strict` valid.) Check scope and `openspec validate 80-m5-decode-kernels --strict`. Verify all kept steps have recorded evidence and any skipped stage has an explicit disposition. Do not commit or push without a new request.
