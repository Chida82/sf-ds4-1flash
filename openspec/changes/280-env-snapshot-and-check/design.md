# Design

## Context

- **Where the reads are.** Motivation and counts: proposal.md, Why. Upstream's style is an inline `getenv("DS4_...")` at the decision site; some helpers take the name as a parameter (`ds4_gpu_env_*`, `metal_graph_tp_env_flag`, the stage-profile pair at `ds4.c` `metal_graph_stage_profile_enabled_for_layer`), always called with a literal.
- **Who writes the environment.** The engine never calls `setenv`, `unsetenv` or `putenv` (no site in `ds4*.c`, `ds4*.m`). The tests do, 188 times across 10 files, between engine calls, to toggle switches and paths.
- **How the code is built.** `CFLAGS` and `OBJCFLAGS` (`Makefile` lines 15-19) reach every engine object (`ds4.o`, `ds4_cpu.o`, `ds4_metal.o`, frontends) and most test objects. Several tests `#include "../ds4.c"`, `../ds4_server.c` or `../ds4_cli.c` and link their own set of objects, through about twenty link rules. A few tests (`q4k-dot`, `mxfp4-dot`, the quality API test) use their own flags and touch no switch.
- **Where the engine opens.** `ds4_engine_open_internal` (`ds4.c`) is the one path the CLI, server, bench, eval and tests take.
- **The harness.** `ab_bench.py` strips inherited `DS4_*` and passes its own `--env`/`--b-env`; it parses stderr only for the lines it knows.

## Goals / Non-Goals

**Goals:**
- No upstream call site changes; new upstream `getenv` sites are covered with no merge work.
- Values identical to `getenv` for the engine's whole life, so output stays bitwise identical.
- A classification that cannot drift silently from the code.

**Non-Goals:**
- Removing or renaming switches, or changing any default.
- Validating switch values (a malformed number keeps today's behaviour).
- Reporting non-`DS4_*` variables (`MTL_*`, `OBJC_*`, `HF_*`).

## Decisions

### D1. Redirect `getenv` with a force-included child header
`ds4_env.h` is passed with `-include ds4_env.h` in `CFLAGS` and `OBJCFLAGS`. It includes `<stdlib.h>` first (so the C library's own declaration is seen before the macro), then defines `#define getenv(name) ds4_env_get(name)`, `#define setenv(n, v, o) ds4_env_setenv(n, v, o)` and `#define unsetenv(n) ds4_env_unsetenv(n)`. `ds4_env_get` returns `char *`, like `getenv`.

- *Alternative: change the call sites* (a `DS4_ENV("...")` macro or a struct of flags read at open). Touches about 400 upstream lines and conflicts at every sync. Rejected.
- *Alternative: cache per call site* (`static` beside each read). Same diff size, and breaks the tests' in-process toggles. Rejected.

### D2. Header-only, with weak definitions
The functions, the snapshot state and the classification table are defined in the header with `__attribute__((weak))`, so every binary built with the flags gets exactly one copy without any link rule naming a new object. Mach-O coalesces weak definitions at link time.

- *Alternative: `ds4_env.c` and `ds4_env.o` in every link rule.* About twenty rules today, and every future test rule would have to remember it; a missed one fails to link, or worse, a test built without the header silently skips the snapshot. Rejected in the spirit of AGENTS.md rule 18: the build should do it, not a note.

### D3. Snapshot of the `DS4_*` entries only
On the first lookup (`pthread_once`) the header scans `environ` once and copies every `DS4_*` entry (name and value) into a small array. `ds4_env_get(name)`:
1. not starting with `DS4_` (four bytes): the C library's `getenv`, unchanged;
2. array empty (the normal case): `NULL`;
3. otherwise: a linear compare over the few entries set.

The test wrappers call the real `setenv`/`unsetenv`, then rebuild the array into a fresh allocation and publish its pointer with a release store; lookups load it with acquire. The old array is never freed: only tests rebuild, a few hundred bytes per toggle, and a thread still reading the old one stays safe.

- *Alternative: snapshot every name the code reads, by index.* Needs the name-to-index map at each call, which is the string compare this avoids. Rejected.

### D4. Classification as an X-macro data file
`ds4_env.def`, one line per variable, sorted by name:

```c
DS4_ENV(DS4_METAL_CB_TIMES, probe, unset, "Print each command buffer's CPU and GPU times to stderr")
```

Categories: `operational` (paths, lock file, replica: set on purpose in normal use), `tuning` (a knob with a measured default), `disable` (turns a speed-up off), `enable` (opt-in experiment), `probe` (timing, profiles, dumps, debug output), `test` (read by tests or test hooks). Normal-use state is `any` for `operational` and `test`, `unset` for the rest unless a line says otherwise. The description is one line written from the read site.

The header expands the file into the table the report uses. The make check reads the same file with `grep`.

- *Alternative: a TSV and a generator.* Friendlier outside C, but adds a build step and C string escaping for nothing a `grep` cannot do. Rejected.

### D5. The name check in `make test`
A first prerequisite of `test`, `env-check`, collects every whole-string literal `"DS4_[A-Z0-9_]+"` in `ds4*.c`, `ds4*.m` and `tests/*.c`, and the names in `ds4_env.def`, then:
- read but not classified: prints them and fails;
- classified but no longer read: prints them and fails;
- otherwise prints `env-check: N DS4_* variables classified`.

The literal rule leaves out messages such as `"DS4_X changed after..."`, because the closing quote must follow the name. A false positive found while classifying (a literal that is not a variable) is excluded by name in the check, with a comment saying why. The pass line follows AGENTS.md rule 19: the output names what ran.

### D6. The report: once per process, at engine open
`ds4_engine_open_internal` calls `ds4_env_report()` once; a static flag makes later opens silent. It walks the snapshot, not the table, so with nothing set it costs nothing. For each set variable:
- classified with state `unset`: `ds4: env DS4_X=1 is set (probe): Print each command buffer's ...`;
- not in the table: `ds4: env DS4_Y=1 is set but this build never reads it`.

Nothing is printed for `any` entries. Tests that set switches see the lines once per test process; the harness ignores unknown stderr lines.

### D7. Steps
- **S1** snapshot (D1-D3) with a stub table: performance step, judged by the harness.
- **S2** classification, check and report (D4-D6): tool step, bitwise, no metric below zero.

## Risks / Trade-offs

- [A system header used after the macro calls `getenv` in an inline function] → it goes through `ds4_env_get`, which passes non-`DS4_*` names to the C library unchanged.
- [Some code reads a `DS4_*` variable after changing it itself] → none today (no `setenv` in the engine); the wrappers keep it correct even if one appears.
- [A test compiled without `CFLAGS` reads switches the engine read through the snapshot] → it gets the C library's live values, which agree because only wrapped `setenv` calls change them.
- [557 descriptions take time to write, and some will be thin] → the description is the read site's meaning in one line; a description that needs more points to the doc that has it (`AGENTS.md`, `perf-record.md`).
- [The gain is at the edge of the harness's resolution] → decode pooled over at least two invocations; the step is kept on the pooled CI rule (under 800 runtime lines: above zero, however small).

## Migration Plan

No defaults change. Rollback is removing the `-include` flag: every call goes back to the C library.
