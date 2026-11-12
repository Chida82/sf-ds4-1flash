# Tasks

Requires `830` and `820`.

## 1. Layout

- [ ] 1.1 `sf_sysone_layout`, `sf_sysone_schema_prefix`, `sf_sysone_schema_state`, `sf_sysone_pointer_suffix`; the extra symbol check in `sf_sysone_open`.
- [ ] 1.2 `sf_sysone_answer_from` takes the layout. `make test-sysone` passes for `state_first` unchanged, and the new model-backed checks pass.

## 2. Server

- [ ] 2.1 `sf.layout` request option and `--sysone-layout`; unknown value → 422.
- [ ] 2.2 Schema cache (`--sysone-schema-cache`), the flow of the design; `sf` response reports `"layout"` and `"schema_cache":"hit"|"miss"`.
- [ ] 2.3 Calibration binding: a file fitted on one layout is never applied to the other. `--sysone-layout` different from the file's layout is a startup error; a request that picks the other layout runs at temperature 1 and its `sf` object says `"calibration":"none"`.

## 3. Measure the layout

- [ ] 3.1 Bench grouping of the design; runs for both layouts; the cost table with measured rows.
- [ ] 3.2 Decide by the acceptance rule. On failure: remove the layout code, keep the record, skip section 4.

## 4. Prior correction

- [ ] 4.1 Prior measurement at schema store; `sf.prior_correction`.
- [ ] 4.2 Bench: `--rotate 0/1` with and without correction; decide by the rule; on failure remove the code and record a rejected row.

## 5. Docs

- [ ] 5.1 `docs/SERVER.md`: the layout, when to use it, the isolation difference from Jev in one plain sentence, stable question order.
- [ ] 5.2 `docs/system-one.md`: "Measured" rows; move approach E from "new here" to its result.
- [ ] 5.3 `sysone-bench/record.md`.
