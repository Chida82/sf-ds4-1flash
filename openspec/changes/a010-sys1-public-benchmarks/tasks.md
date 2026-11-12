# Tasks

Requires `810`, `820`. Standard-library Python; install nothing; never run code from a downloaded repository.

## 1. Data

- [ ] 1.1 Fetch the three sources into `--work`; licence and revision of each in the record. Stop a set without a licence.
- [ ] 1.2 `convert.py --source jevbench|jevify` with the field mapping in a comment; the unit test; `make test` passes and names it.

## 2. Runs

- [ ] 2.1 `td-full`: sysone on all 2,000 decisions; fit on even ids, score odd ids raw and calibrated; `think` on 60.
- [ ] 2.2 `jevbench-231`: the same three modes.
- [ ] 2.3 `jevify`: `policy-29`, `policy-hard-52`, then `long-state-24` alone with prefill times.

## 3. Record

- [ ] 3.1 "Public benchmarks" table with published scores, URLs, skipped counts, the caption about model-generated labels.
- [ ] 3.2 The per-set verdicts and the overall line; the latency comparison.
- [ ] 3.3 `docs/system-one.md` section 8: the table and the verdict.
