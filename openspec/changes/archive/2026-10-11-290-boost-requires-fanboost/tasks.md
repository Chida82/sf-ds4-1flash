# Tasks

Work in a worktree branched from `main`. Task 1 changes the owner's fanboost repository and needs the owner's go-ahead for that repository.

## 1. `fanboost check` (design D1)

- [x] 1.1 In the owner's fanboost repository: `fanboost check` exits 0 when the daemon is running and 1 with one stderr line otherwise; add it to `help`, the README command table and the spec. Verify `make test` prints `ok`, `fanboost check; echo $?` prints 0 with the daemon running, and a scratch copy pointed at an unused notification name exits 1 with its message.
- [x] 1.2 Copy `fanboost.c` into `fanboost/` here and add the `check` row to `fanboost/README.md`. Verify `diff` against the owner's file is empty and a scratch build of `fanboost/` passes `make test`.

## 2. Engine (design D2-D4)

- [x] 2.1 `int ds4_gpu_set_boost(bool)` with the check and the three messages (D2), and the engine-open failure path in `ds4_engine_open_internal`. Verify `make` has no warning and `make test` names its tests.
- [x] 2.2 The single runtime warning in `ds4_gpu_fan_hint` (D3). Verify by reading the diff that the keep-alive path is untouched.
- [x] 2.3 Missing and down cases on scratch builds (D4): the CLI with `--boost` built against `/nonexistent/fanboost` prints the "not installed" line and exits non-zero before the loader's first line; a scratch fanboost whose `check` exits 1 gives the "not running" line. Verify both with `echo $?` and the stderr line, and that a run without `--boost` on the same scratch build starts normally.
- [x] 2.4 On the real machine with fanboost running: CLI and server start with `--boost`, `fanboost` logs `richiesta: max` before the model loads, and output is token-identical to a run without `--boost` on one prompt. Verify from the log and a `cmp` of the two outputs.

## 3. Documentation

- [x] 3.1 `ds4_help.c` (`--boost` line), the README `--boost` paragraph and `AGENTS.md` (Fan hint) say that `--boost` needs fanboost and refuses without it, and name `DS4_METAL_V41_DECODE_KEEPALIVE=1` in `AGENTS.md` for the keep-alive alone. Verify `./sf-ds4-1flash --help | grep -- --boost` shows the new line.
- [x] 3.2 `openspec validate 290-boost-requires-fanboost --strict`. Verify it passes. No commit or push without a request.
