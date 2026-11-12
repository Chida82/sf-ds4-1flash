# Tasks

Requires `800`, `810`, `820`. Do not edit `ds4.c`, `ds4_metal.m` or `ds4.h`.

## 1. Token-level escape

- [ ] 1.1 Read `ds4_tokenize_text` in `ds4.c`; write in the record whether special-token text can become a special id.
- [ ] 1.2 `tests/test_sysone MODEL --special-text` with one named line per token; run it.
- [ ] 1.3 Only on a failure: the U+FF5C replacement in `sf_sysone_state_prefix`, a model-less unit test of the replacement, re-run 1.2, note for the owner about the chat path.

## 2. Flip rate

- [ ] 2.1 `sysone-bench/inject.py` and a unit test in `tests/test_sysone_bench.py` (wrong-symbol choice, Italian sentence, score skipped).
- [ ] 2.2 Run clean and attacked on `fixtures-it.jsonl` and the `typed-decisions` test split; table in the record.

## 3. Mitigation (only if a flip rate is at least 5%)

- [ ] 3.1 M1 and M2 as scratch template builds; run both; apply the gate.
- [ ] 3.2 On a winner: new template version in `sf_sysone.c`, calibration re-fit, `docs/system-one.md` and `docs/SERVER.md` mention the mitigation.
