# Tasks

Requires `830` and `820`.

## 1. Layout

- [x] 1.1 `sf_sysone_layout` (not needed: the pointer suffixes go through `sf_sysone_answer_suffixes`), `sf_sysone_schema_prefix`, `sf_sysone_schema_state`, `sf_sysone_pointer_suffix` (the revised pointer suffix of the design: no prefill, no extra symbol check).
- [x] (Not done: layout dropped by 3.2, archived as rejected.) 1.2 `sf_sysone_answer_from` takes the layout. `make test-sysone` passes for `state_first` unchanged, and the new model-backed checks pass.

## 2. Server

- [x] (Not done: layout dropped by 3.2, archived as rejected.) 2.1 `sf.layout` request option and `--sysone-layout`; unknown value → 422.
- [x] (Not done: layout dropped by 3.2, archived as rejected.) 2.2 Schema cache (`--sysone-schema-cache`), the flow of the design; `sf` response reports `"layout"` and `"schema_cache":"hit"|"miss"`.
- [x] (Not done: layout dropped by 3.2, archived as rejected.) 2.3 Calibration binding: a file fitted on one layout is never applied to the other. `--sysone-layout` different from the file's layout is a startup error; a request that picks the other layout runs at temperature 1 and its `sf` object says `"calibration":"none"`.

## 3. Measure the layout

- [x] 3.1 Bench sets of the revised design (system-one-bench suites as same-question streams, jevbench groups, fixtures); `schema_first` runs, compared with the `a010` `state_first` rows of the same items; the cost table with measured rows.
- [x] 3.2 Decide by the acceptance rule. On failure: remove the layout code, keep the record, skip section 4.

## 4. Prior correction

- [x] (Not done: layout dropped by 3.2, archived as rejected.) 4.1 Prior measurement at schema store; `sf.prior_correction`.
- [x] (Not done: layout dropped by 3.2, archived as rejected.) 4.2 Bench: `--rotate 0/1` with and without correction; decide by the rule; on failure remove the code and record a rejected row.

## 5. Docs

- [x] (Not done: layout dropped by 3.2, archived as rejected.) 5.1 `docs/SERVER.md`: the layout, when to use it, the isolation difference from Jev in one plain sentence, stable question order.
- [x] (Not done: layout dropped by 3.2, archived as rejected.) 5.2 `docs/system-one.md`: "Measured" rows; move approach E from "new here" to its result.
- [x] (Not done: layout dropped by 3.2, archived as rejected.) 5.3 `sysone-bench/record.md`.

## Progress (2026-11-24, overnight)

Order changed so the server work is built only if the layout passes: the
layout functions (1.1, without the server's schema cache) and a measuring
mode, `tests/test_sysone MODEL --schema-first ITEMS OUT`, which keeps one
schema snapshot per run of consecutive items sharing a question, as the
schema cache would. `sysone-bench/schema_first.py` compares it with the
`a010` `state_first` rows of the same items and applies the acceptance rule.
First run: the first 60 items of each system-one-bench suite (420). Sections
2 and 4 wait for that verdict.

Verdict (2026-11-24, 05:30): **dropped by the rule.** Accuracy level
(−0.012, −0.043 to +0.019), latency p50 −34% where the rule asks −50%; BoolQ
slower than `state_first` because a sub-256-token state appended to a cached
prefix runs token by token. Layout code removed, re-apply patch
`dropped-layout.patch` in this directory. Sections 1.2, 2 and 4 not done
(section 4, prior correction, depended on the layout; `a020` measured the
prior on `state_first` instead). Left open for the owner: archive as
rejected, or revise (for example, a state padded or batched to a sweep).

Archived as rejected (owner, 2026-11-24). Specs not applied (`--skip-specs`);
the layout can be re-applied from `dropped-layout.patch` here.
