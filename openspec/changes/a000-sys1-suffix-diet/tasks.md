# Tasks

Follow `design.md` section by section; every name, string and threshold is
there. Do not edit `ds4.c`, `ds4_metal.m` or `ds4.h`. One model process at a
time. Do not commit.

## 1. Template id (design: "Code, step A")

- [ ] 1.1 Save `W/tokens-before.txt` with `tests/test_sysone MODEL --tokens` before any edit.
- [ ] 1.2 `sf_sysone.h/.c`: `template_version` argument of `sf_sysone_open`, `sf_sysone_template`, the five suffix builders (ids 1, 91-94).
- [ ] 1.3 `ds4_server.c`: `--sysone-template`, the `template_version` parameter of `sysone_response_json` and `sysone_calibration_parse`, their callers; `ds4_help.c` line.
- [ ] 1.4 `sysone-bench/fit.py`: `--template-version` (default 1).
- [ ] 1.5 `make`, `make test` (read the test lines), `./ds4_test --server`, `make test-sysone`; `diff` of the token dump before and after is empty.

## 2. Probe (design: "Code, step B", "Run 1")

- [ ] 2.1 `--suffix-probe` mode in `tests/test_sysone.c`.
- [ ] 2.2 Run it; table and survivors in `sysone-bench/record.md`, section "Suffix diet (a000)". No survivor: go to 5.

## 3. Bench and gate (design: "Run 2", "Gate script", "Choosing the winner")

- [ ] 3.1 `sysone-bench/template_gate.py` and its unit test in `tests/test_sysone_bench.py`; `make test`.
- [ ] 3.2 Build `td500.jsonl` and `td500-choice.jsonl`; run template 1 and each survivor on `fixtures-it.jsonl` and `td500.jsonl`.
- [ ] 3.3 Gate each survivor; pick the candidate; rotation runs for template 1 and for it; gate with rotation; repeat with the next candidate on a flip-rate failure.
- [ ] 3.4 Table with every candidate's gate values, paired right→wrong and wrong→right counts, and the decision in `sysone-bench/record.md`.

## 4. Freeze (only with a winner; design: "Freezing")

- [ ] 4.1 Renumber the winner to 2, delete the other candidates and `--suffix-probe`; default version 2; `mode_checks` for both versions; server unit test for the version check; `fit.py` default 2.
- [ ] 4.2 `make`, `make test`, `./ds4_test --server`, `make test-sysone`; one live request showing `"template_version":2`.
- [ ] 4.3 Re-fit the calibration for version 2 and record its temperatures; `docs/system-one.md` section 7.

## 5. No winner (instead of 4; design: "No winner")

- [ ] 5.1 Revert the six code files, keep the gate script and the record, add the paragraph to `docs/system-one.md` section 7, `make test`.
