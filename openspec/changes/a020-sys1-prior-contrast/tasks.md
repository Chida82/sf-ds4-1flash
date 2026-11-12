# Tasks

Requires `820`. Section 3 requires `a015` kept.

- [ ] 1.1 `run.py --blank-state` (dedupe per distinct question and rotation; under `schema_first` blank inside the same grouped request).
- [ ] 1.2 `contrast_fit.py` with both priors, the β grid, state-level split and paired bootstrap; unit tests in `tests/test_sysone_bench.py`: β = 0 equals the baseline; a synthetic set with a planted option bias recovers β near 1 and removes the flips.
- [ ] 2.1 Blank-state runs for each layout in use, rotations 0 and 1.
- [ ] 2.2 The fit; one table per layout in `sysone-bench/record.md`; apply the gate and write the decision.
- [ ] 3.1 On "keep" with `a015`: `prior_beta` in the calibration file, its loader, the factor in `sf_sysone.c`, the unit test.
- [ ] 3.2 `docs/system-one.md`: the result, and the sentence that a015's β = 1 is one point of this family. `docs/SERVER.md` if 3.1 was done.
