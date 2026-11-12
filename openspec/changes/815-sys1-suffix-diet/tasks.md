# Tasks

Requires `800`, `810`, `820`. Do not edit `ds4.c`, `ds4_metal.m` or `ds4.h`.

## 1. Probe

- [ ] 1.1 Candidates D0-D4 in the probe table of `tests/test_sysone.c` (one-string tokenization for D1-D4); the probe prints mean suffix tokens.
- [ ] 1.2 Run the probe; drop candidates under minimum legal mass 0.9; paste the table into `sysone-bench/record.md`.

## 2. Bench

- [ ] 2.1 For each survivor: scratch build as template 2, server, `run.py --mode sysone` and `--rotate 1` on both sets.
- [ ] 2.2 Apply the gate; write the table and the decision.

## 3. Freeze (only on a winner)

- [ ] 3.1 Template table with versions 1 and 2 in `sf_sysone.c`; `sf_sysone_open` takes the version; `--sysone-template` in `ds4_server.c` and `ds4_help.c`.
- [ ] 3.2 `make test`, `make test-sysone` (both versions), `./ds4_test --server`.
- [ ] 3.3 Re-fit the calibration for version 2; `docs/system-one.md` section 7 gains the version-2 layout and the token saving.
