# Tasks

Requires `810`, `820`. Standard-library Python; install nothing; never run code from a downloaded repository.

## 1. Data

- [x] 1.1 Fetch the three sources into `--work`; licence and revision of each in the record. Stop a set without a licence.
- [x] 1.2 `convert.py --source jevbench|jevify` with the field mapping in a comment; the unit test; `make test` passes and names it.
- [ ] 1.3 `run.py --effort` (default `high`) and per row `completion_tokens`, `finish_reason`, reasoning length; report p50/p95 completion tokens; unit test that the answer comes from `content` only.
- [ ] 1.4 `sysone-bench/jb_compare.py` (per-item accuracy, discordant pairs, exact sign test) and its unit test on a hand-written two-system file.

## 2. Runs

- [ ] 2.1 `td-full`: sysone on the 1,500 decisions `td500` does not cover (reuse the `a000` template-2 rows); fit on even ids, score odd ids raw and calibrated; `think --effort medium` on every tenth decision (200).
- [ ] 2.2 `jevbench-231`: sysone (done, see Progress), calibration halves, `think --effort medium` on all 231.
- [ ] 2.3 `jevify`: `policy-29`, `policy-hard-52` (sysone done) with calibration and `think --effort medium`; `long-state-24` sysone only (done).
- [ ] 2.4 Quantization check: `jb_compare.py` of our jevbench `think` against "DeepSeek V4.1 Flash (thinking default)"; if the gap rule fires, rerun the disagreeing items at `--effort high`.

## 3. Record

- [ ] 3.1 "Public benchmarks" table with the five reference columns (empty where nothing is published), URLs, versions, skipped counts, the sealed-set note, the caption about model-generated labels.
- [ ] 3.2 The per-set verdicts (plain and think), the overall line, the quantization line, the latency comparison.
- [ ] 3.3 `docs/system-one.md` section 8: the table and the verdict.

## Progress (2026-11-13, overnight run)

- Done in `sysone-bench/record.md`, "Public benchmarks (a010, in progress)": sources, licences, revisions; plain readout on `policy-29`, `policy-hard-52`, `jevbench-231` and `long-state-24`.
- The old jevbench reference (76.2%) was not traceable; the design now takes the references from jevbench's own per-item and aggregate result files. The record's "Public benchmarks (a010, in progress)" verdict lines predate that and are rewritten in 3.2.
- Still to do: `td-full` (reuse `820`'s td500 rows only if run on template 2: the a000 run `r-td-2.jsonl` was), calibration halves per set, `think` on 60 per set, `docs/system-one.md` section 8, the overall line.
