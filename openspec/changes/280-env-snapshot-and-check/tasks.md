# Tasks

Work in a worktree branched from `main`, never on `main`. A/B runs never edit the B tree while they run.

## 1. S1: read once (design D1-D3)

- [ ] 1.1 `ds4_env.h` with the `getenv`/`setenv`/`unsetenv` redirection, the `DS4_*` snapshot and its rebuild (D1-D3), all definitions weak; `-include ds4_env.h` in `CFLAGS` and `OBJCFLAGS`. Verify `make` and `make cpu` build with no new warning, and `nm` shows one `ds4_env_get` definition per binary.
- [ ] 1.2 Behaviour checks in `make test` (a small test, model-less): a `DS4_*` set before the first lookup is seen; a toggle through `setenv`/`unsetenv` between two lookups is seen; a non-`DS4_*` name returns what the C library returns; with no `DS4_*` set the lookup returns `NULL`. Verify the test's PASS line appears in `make test` output, and that the existing test suite still names all its tests (`make test` output, rule 19).
- [ ] 1.3 `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_READBACK_MAILBOX` and one tuning knob (`DS4_METAL_STREAMING_EXPERT_HOTNESS_DECAY_TOKENS=128`) on the S1 build. Verify both run and report their usual bitwise result, which shows the snapshot delivers set switches to the engine.
- [ ] 1.4 Harness: A = `main` (the segment start, after an A/A row if the segment has none), B = S1, kinds `decode,append,cold-5000`, `--bitwise`, 3600 s, two invocations pooled. Verify bitwise and apply the keep rule (under 800 runtime lines: target decode CI above zero, no throughput CI wholly below zero); repeat once with a longer decode budget if inconclusive. Record the rows in `speed-bench/perf-record.md`.

## 2. S2: classification, check and report (design D4-D6)

- [ ] 2.1 Inventory: the whole-string `"DS4_[A-Z0-9_]+"` literals in `ds4*.c`, `ds4*.m` and `tests/*.c`. Review the list and exclude any literal that is not a variable. Verify the count is recorded in the `perf-record.md` section and every excluded literal has its reason in the check.
- [ ] 2.2 `ds4_env.def`: one `DS4_ENV(name, category, state, "description")` line per variable, sorted. Category and state per D4; description from the read site in one line. Start from the name patterns (`DISABLE_`, `ENABLE_`, `PROFILE`/`TIMES`/`TIMING`/`TRACE`/`DUMP`/`DEBUG`/`SUMMARY`, `TEST`), then read every site, and do not trust a pattern alone (AGENTS.md, Names that lie). Verify no line has an empty description, and that the operational set includes at least `DS4_LOCK_FILE` and `DS4_METAL_PREFILL_REPLICA`.
- [ ] 2.3 `env-check` as the first prerequisite of `test` (D5). Verify it prints `env-check: N DS4_* variables classified`; that deleting one `.def` line makes `make test` fail naming it; that adding a fake `getenv("DS4_SF_ENV_CHECK_PROBE")` to a scratch copy makes it fail naming that; and that `grep -c '^test:' Makefile` is still 1.
- [ ] 2.4 `ds4_env_report()` and its one call in `ds4_engine_open_internal` (D6). Verify on the CLI with a short prompt: a clean environment prints no `ds4: env` line; `DS4_METAL_CB_TIMES=1` prints one line with category `probe` and its description; `DS4_SF_NOT_A_SWITCH=1` prints the "never reads it" line; `DS4_METAL_PREFILL_REPLICA` alone prints nothing.
- [ ] 2.5 Harness: A = S1, B = S2, kinds `decode,append`, `--bitwise`, 1800 s. Verify bitwise and no metric with its CI wholly below zero (tool step).
- [ ] 2.6 `AGENTS.md`, "Child-specific values": the `DS4_*` paragraph says where the classification lives, what the startup report prints, and that a sync with a new switch stops at `env-check` until it is classified. Verify the paragraph names `ds4_env.def` and `env-check`.

## 3. Integration

- [ ] 3.1 Final review over `ds4_env.h`, `ds4_env.def`, the Makefile and the `ds4.c` call, against `AGENT.md` and the surrounding idiom; delete what the change made dead. Verify `make`, `make cpu` and `make test` (output names its tests and `env-check`).
- [ ] 3.2 Model-backed checks: `make test-deepseek41-metal`, `ds4_test` with streaming (by name, skipping the `--all` quality branch), `./sf-ds4-1flash-eval --ssd-streaming --suite core`, and from the StarForge checkout `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`. Verify parity is token-identical.
- [ ] 3.3 A/B against the segment start in `perf-record.md`, append the printed row, and `openspec validate 280-env-snapshot-and-check --strict`. Verify validation passes. No commit or push without a request.
