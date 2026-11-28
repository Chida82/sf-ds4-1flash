# Tasks

Requires `810`, `820`, `835`. Do not edit `ds4.c`, `ds4_metal.m` or `ds4.h`.

## 1. Rotation averaging

- [ ] 1.1 `sysone-bench/rotation_avg.py` and its unit test in `tests/test_sysone_bench.py`.
- [ ] 1.2 Rotation 1 on every `choice` item of the `a010` sets (rotation 0: the `a010` plain rows); the table raw and calibrated; apply the rule; record.

## 2. Chained questions

- [ ] 2.1 `sf_sysone_answer_chained`; the `"-"` single-token assert at open; `"sf":{"chain":true}` in the server with its parse test and the 422 with `live`.
- [ ] 2.2 `make test-sysone`: the two named bitwise lines.
- [ ] 2.3 `convert.py --source s1b-pairs` and its unit test; `run.py --reverse-questions`; isolated, chained, chained reversed on all `s1b-sst5-pairs` states.
- [ ] 2.4 Per-position table; apply the rule; on "drop" remove the option and function; on "keep" write the break-even count for a multi-row sweep readout.

## 3. Graded noul

- [ ] 3.1 The graded suffix and readout behind `"sf":{"noul":"graded"}`; model-less unit test of the expectation; parse test.
- [ ] 3.2 Two-letter against graded on all `noul` items of the `a010` sets and the fixtures; apply the rule; on "drop" remove the code.

## 4. Records

- [ ] 4.1 `a035` design and tasks: the `max_share` cap.
- [ ] 4.2 `docs/system-one.md` section 11: the three probe results beside the survey table; `docs/SERVER.md` for any option kept.
