# Tasks

Read `docs/system-one.md` and `design.md` before starting. Do not edit
`ds4.c`, `ds4_metal.m` or `ds4.h` in this change.

## 1. Math

- [x] 1.1 `sf_sysone.h` with the interface in the design; `sf_sysone.c` with `sf_sysone_finish` only.
- [x] 1.2 `tests/test_sysone.c`: the model-less checks; `Makefile`: `sf_sysone.o`, `tests/test_sysone` linked like `tests/test_deepseek41_graph`, both added to `test:` and run there as `./tests/test_sysone`.
- [x] 1.3 After the Makefile edit: `grep -c '^test:' Makefile` prints 1 and `make -n test | grep test_sysone` prints the line. `make test` passes and its output names `test_sysone`.

## 2. Tokens and prompt

- [x] 2.1 `sf_sysone_open` / `_close`: the two symbol checks of the design.
- [x] 2.2 `sf_sysone_state_prefix`, `sf_sysone_question_suffix`: piece by piece, never one concatenated string.
- [x] 2.3 Model-backed `--tokens` mode in the test: prints the tokens of fixture 1 (prefix, suffix) with `ds4_token_text`; check by eye that the prefix tokens are the first tokens of prefix+suffix.

## 3. Template probe

- [x] 3.1 `tests/test_sysone --probe` with the T-A/T-B/T-C table and the 12 fixtures.
- [x] 3.2 Run it (`--ssd-streaming` settings as in the design). Paste the three result rows into `docs/system-one.md`, new section "Template".
- [x] 3.3 Freeze the winner in `sf_sysone.c`. If no candidate reaches mean legal mass 0.5: stop and ask.

## 4. Decide

- [x] 4.1 `sf_sysone_decide`: sync, snapshot, per-question restore and readout, the refusals.
- [x] 4.2 `Makefile`: `test-sysone` target and its line in `make help`.
- [x] 4.3 `make test-sysone`: symbols, fixtures, isolation, determinism, restore position. Every check prints a named line.

## 5. Close

- [x] 5.1 `make test` passes; `make cpu` still builds (the module must compile without Metal: it only calls `ds4.h`).
- [x] 5.2 `docs/system-one.md`: "Template" section (probe rows, the frozen layout, measured milliseconds for a 60-token state and a 600-token state with three questions).
- [x] 5.3 `docs/MODEL_KNOWLEDGE.md`, "Interfaces that do not exist": replace "a classification head" by a pointer to `sf_sysone.h`.
