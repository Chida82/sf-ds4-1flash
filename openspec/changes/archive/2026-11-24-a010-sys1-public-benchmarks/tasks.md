# Tasks

Requires `810`, `820`. Standard-library Python; install nothing; never run code from a downloaded repository.

## 1. Data

- [x] 1.1 Fetch the three sources into `--work`; licence and revision of each in the record. Stop a set without a licence.
- [x] 1.2 `convert.py --source jevbench|jevify` with the field mapping in a comment; the unit test; `make test` passes and names it.
- [x] 1.3 `run.py --effort` (default `high`) and per row `completion_tokens`, `finish_reason`, reasoning length; report p50/p95 completion tokens; unit test that the answer comes from `content` only.
- [x] 1.4 `sysone-bench/jb_compare.py` (per-item accuracy, discordant pairs, exact sign test) and its unit test on a hand-written two-system file.
- [x] 1.5 `convert.py --source s1b`: rebuild each suite as `build_suites.py` does, refuse a suite whose hash differs from `data.lock.json`; unit test.

## 2. Runs

- [x] 2.1 `s1b`: `convert.py --source s1b` (hash-checked); sysone on all 1,300 items; fit on even ids, score odd ids raw and calibrated; `think --effort medium` on the first 30 of each suite (210).
- [x] 2.2 `jevbench-231`: sysone (done, see Progress), calibration halves, `think --effort medium` on all 231.
- [x] 2.3 `jevify`: `policy-29`, `policy-hard-52` (sysone done) with calibration and `think --effort medium`.
- [x] 2.4 Quantization check: `jb_compare.py` of our jevbench `think` against "DeepSeek V4.1 Flash (thinking default)"; if the gap rule fires, rerun the disagreeing items at `--effort high`.

## 3. Record

- [x] 3.1 "Public benchmarks" table with the five reference columns (empty where nothing is published), URLs, versions, skipped counts, the sealed-set note, the caption about model-generated labels.
- [x] 3.2 The per-set verdicts (plain and think), the overall line, the quantization line, the latency comparison.
- [x] 3.3 `docs/system-one.md` section 8: the table and the verdict.

## Progress

Done 2026-11-24 (overnight). Results and verdict: `sysone-bench/record.md`,
"Public benchmarks (a010, 2026-11-24)"; summary in `docs/system-one.md`
section 8. Two bench bugs found and fixed on the way: jevbench `easy` items had
no state id (one bootstrap cluster), and a thinking parse failure tied to the
first option.
