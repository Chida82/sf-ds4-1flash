# Design

## Context

- **Where the reads are.** Motivation and counts: proposal.md, Why. Upstream's style is an inline `getenv("DS4_...")` at the decision site; some helpers take the name as a parameter (`ds4_gpu_env_*`, the stage-profile pair at `ds4.c` `metal_graph_stage_profile_enabled_for_layer`), always called with a literal.
- **Who writes the environment.** The engine never calls `setenv`, `unsetenv` or `putenv` (no site in `ds4*.c`, `ds4*.m`). The tests do, 188 times across 10 files, between engine calls, to toggle switches and paths.
- **Where the engine opens.** `ds4_engine_open_internal` (`ds4.c`) is the one path the CLI, server, bench, eval and tests take.
- **The harness.** `ab_bench.py` strips inherited `DS4_*` and passes its own `--env`/`--b-env`; it parses stderr only for the lines it knows.

## Goals / Non-Goals

**Goals:**
- Control: every switch classified, the build stops on a new one, a run shows what is set out of its normal state.
- No phase slower, output bitwise identical. The change claims no speed.
- Two upstream lines (`ds4.c`: the include and the call); new upstream `getenv` sites need no merge work, only a `.def` line.
- A classification that cannot drift silently from the code.

**Non-Goals:**
- Changing how switches are read (D1).
- Renaming switches or changing any default.
- Validating switch values (a malformed number keeps today's behaviour).
- Reporting non-`DS4_*` variables (`MTL_*`, `OBJC_*`, `HF_*`).

## Decisions

### D1. Switches keep reading the live environment
The first step (S1) redirected every `getenv` through a force-included header to a once-per-process snapshot of the `DS4_*` entries, with `setenv`/`unsetenv` wrappers so tests could still toggle. The `130` profile put `getenv` at 0.5% of decode. Two harness invocations against `main`, pooled, measured decode 2048 +0.13% (-0.91..+0.40) and decode 8192 -0.29% (-0.61..-0.11): no gain. The snapshot, its wrappers and their test were dropped. The figures are in `speed-bench/perf-record.md`.

### D2. One header, included by `ds4.c` only
`ds4_env.h` holds the table and the report as `static` definitions, and `ds4.c` includes it. The report has one caller, so each object that compiles `ds4.c` (the engine, and the tests that `#include "../ds4.c"`) carries its own copy.

- *Alternative: `-include ds4_env.h` in `CFLAGS`.* Reaches every object for one caller. Rejected.

### D3. Classification as an X-macro data file
`ds4_env.def`, one line per variable, sorted by name:

```c
DS4_ENV(DS4_METAL_CB_TIMES, probe, unset, "Print each command buffer's CPU and GPU times to stderr")
```

Categories: `operational` (paths, lock file, replica: set on purpose in normal use), `tuning` (a knob with a measured default), `disable` (turns a speed-up off), `enable` (opt-in experiment), `probe` (timing, profiles, dumps, debug output), `test` (read by tests or test hooks). Normal-use state is `any` for `operational` and `test`, `unset` for the rest unless a line says otherwise. The description is one line written from the read site.

The header expands the file into the table the report uses. The make check reads the same file.

- *Alternative: a TSV and a generator.* Friendlier outside C, but adds a build step and C string escaping for nothing a line match cannot do. Rejected.

### D4. The name check in `make test`
A first prerequisite of `test`, `env-check`, collects every whole-string literal `"DS4_[A-Z0-9_]+"` in `ds4*.c`, `ds4*.m` and `tests/*.c`, and the names in `ds4_env.def`, then:
- read but not classified: prints them and fails;
- classified but no longer read: prints them and fails;
- otherwise prints `env-check: N DS4_* variables classified`.

The literal rule leaves out messages such as `"DS4_X changed after..."`, because the closing quote must follow the name. A false positive found while classifying (a literal that is not a variable) is excluded by name in the check, with a comment saying why. The pass line follows AGENTS.md rule 19: the output names what ran.

### D5. The report: once per process, at engine open
`ds4_engine_open_internal` calls `ds4_env_report()` first; a static flag makes later opens silent. It walks `environ` and looks up only the `DS4_*` entries in the table, so with nothing set it prints nothing. For each set variable:
- classified with state `unset`: `ds4: env DS4_X=1 is set (probe): Print each command buffer's ...`;
- not in the table: `ds4: env DS4_Y=1 is set but this build never reads it`.

Nothing is printed for `any` entries. Tests that set switches see the lines once per test process; the harness ignores unknown stderr lines.

### D6. Steps
- **S1** snapshot: measured, dropped (D1).
- **S2** classification, check and report (D3-D5), and the dead switches: tool step, bitwise, no metric with its CI wholly below zero against `main`.

## Risks / Trade-offs

- [557 descriptions take time to write, and some will be thin] → the description is the read site's meaning in one line; a description that needs more points to the doc that has it (`AGENTS.md`, `perf-record.md`).
- [A dead-switch cut removes code a test or a run still reaches] → a proof per variable (tasks 2.7), then `ds4_test`, `test-deepseek41-metal` and the parity oracle, token-identical.

## Migration Plan

No defaults change. Rollback is removing the include and the call in `ds4.c`.
