# Tasks

Requires `800`, `810`. Do not edit `ds4.c`, `ds4_metal.m` or `ds4.h`.

## 1. Clocks

- [ ] 1.1 `sf_sysone_timing`, the extra argument, `restore_ms`, `eval_ms`; every existing caller passes NULL.
- [ ] 1.2 Server `sf` fields and the updated golden string; `./ds4_test --server` passes.
- [ ] 1.3 `make test` passes and names `test_sysone`.

## 2. Measure

- [ ] 2.1 `tests/test_sysone MODEL --timing` as in the design, including the bitwise check timing on/off.
- [ ] 2.2 Run it twice (two processes); keep both outputs.

## 3. Record

- [ ] 3.1 `docs/system-one.md`: section "Branch cost" with the median table and the outcome of the three rules.
- [ ] 3.2 If rule 1 fires: write `a081-sys1-branch-restore` (proposal, design, spec, tasks) after reading `ds4_session_load_snapshot`.
