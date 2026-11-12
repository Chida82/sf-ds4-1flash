# Tasks

Requires `830`.

## 0. Establish the prefix fact

- [x] 0.1 List the functions `generate_job_inner` uses to reach the prompt (PR text).
- [x] 0.2 The two measurements (thinking off, thinking high) with the temporary log line; remove the line.
- [x] 0.3 Apply the outcome rule of the design. On "neither reuses": stop and report.

## 1. Feature

- [x] 1.1 Parsing of `sf.state` = `messages` and the message array; unit tests.
- [x] 1.2 `sf_sysone_turn_suffix`; `sf_sysone_answer_from` accepts the `live` layout.
- [x] 1.3 `sysone_job` flow; `reused_tokens` and `layout` in `sf`; calibration not applied across layouts.

## 2. Measure

- [x] 2.1 The live test. (2026-11-12: the checks ran against the live server from a scratch script — reuse 76/77, prefill 152 ms, bitwise repeat, next chat 76 cached, tool role 422; the same checks were then added to `tests/test_sysone_http.py`; full run of the file passed at 06:10.)
- [x] 2.2 `run.py --scenario live`; the row in `sysone-bench/record.md`; apply the keep rule (on failure remove the feature, keep the record).

## 3. Docs

- [x] 3.1 `docs/SERVER.md`: the option, what is reused and when it is not (the step 0 finding, in plain words).
- [x] 3.2 `docs/system-one.md`: the result.
