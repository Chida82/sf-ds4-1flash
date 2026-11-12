# Tasks

Requires `810`. Standard-library Python only; do not install packages.

## 1. Tooling

- [x] 1.1 `sysone-bench/metrics.py` and `tests/test_sysone_bench.py`; add the test to `make test` next to `tests/test_ab_bench.py`. Check `grep -c '^test:' Makefile` is 1 and the test's name appears in `make test` output.
- [x] 1.2 `sysone-bench/run.py` with the four modes and `--rotate`.
- [x] 1.3 `sysone-bench/fit.py`.
- [x] 1.4 `sysone-bench/fixtures-it.jsonl`: 60 items as specified; every label checked by reading the item, not generated blindly.
- [x] 1.5 `sysone-bench/convert.py` for `typed-decisions`; record the dataset id, licence and split sizes in `sysone-bench/README.md`. If the set cannot be identified, stop this task, note it in `record.md`, continue with the fixtures.

## 2. Server flag

- [x] 2.1 `--sysone-calibration FILE`: parse, binding check at startup, temperature passed per type; `ds4_help.c` text.
- [x] 2.2 Unit tests: a matching file loads; each mismatching binding field refuses with a message naming it.
- [x] 2.3 `sf.temperature` override and the `temperature` echo in the response's `sf` object.

## 3. Baseline

- [x] 3.1 Start the server: `./sf-ds4-1flash-server --ssd-streaming --ctx 32768 --ssd-streaming-cache-experts 82GB`. No `--boost`.
- [x] 3.2 The five runs of the design on both sets. Keep every `results.jsonl` in the `--work` directory.
- [x] 3.3 `sysone-bench/record.md`: the table, the three stated numbers, the command lines, the commit and the date.
- [x] 3.4 Commit nothing but `fixtures-it.jsonl`, the scripts, the README and `record.md` (and only when the owner asks for a commit).

## 3b. Baselines for later changes

- [x] 3b.1 `state_id` in every item file; the bootstrap resamples states (unit test: two items of one state always travel together).
- [x] 3b.2 `abstain_items.py` and the four AUROC figures on at least 400 states; the sentence in `record.md`.
- [x] 3b.3 The two schedule runs on 100 items; `delta95` and the top-change share in `record.md`; `SF_SYSONE_DELTA95` and `"unstable"` in the `sf` object, with a unit test on fixed logits.

## 4. Docs

- [x] 4.1 `docs/system-one.md`: section "Measured" with the baseline table and the three numbers.
- [x] 4.2 `docs/MODEL_KNOWLEDGE.md`, "Known unknowns": remove the lines this run answered (calibration, latency of a one-token answer) and point to `sysone-bench/record.md`.
- [x] 4.3 `docs/SERVER.md`: the flag.
