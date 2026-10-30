# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request.

## 1. Baseline

- [x] 1.1 On a worktree of main, build and record the D6 baseline: `./sf-ds4-1flash --ssd-streaming --steering-profile sf-ds4-1flash-candor` on one fixed prompt, greedy, thinking on and off. Keep the two texts and the engine-open stderr lines (`V4.1 residual steering`, `rank-2`). Verify both files exist and the rank-2 line is present.

## 2. Engine

- [x] 2.1 `ds4.h`/`ds4.c`: remove the four sf option fields and their checks, fills and environment gate block, and reduce the profile conflict check (design D2). Verify `make` builds with no warning, and that `git grep -n "allow_v41_steering\|directional_steering_residual2\b\|DS4_STEERING_THINK_PHASE\|DS4_ALLOW_V41_STEERING" -- '*.c' '*.h' '*.m'` is empty.
- [x] 2.2 Rewrite the V4.1 support check as design D1: upstream's line unchanged plus the profile term. Verify the expression with `git diff upstream/main -- ds4.c` at that site, which shows only the added term and its comment.
- [x] 2.3 Check that a profile's second slot still loads through `e->directional_steering_file2` (`ds41_steering_profile_open` → `cpu_load_directional_steering`). Verify by reading both functions and recording the answer in this change's design.

## 3. Frontends

- [x] 3.1 CLI: delete the four sf branches (design D3). Verify `./sf-ds4-1flash --dir-steering-residual 1` exits 2 with "unknown option", and that `--dir-steering-file x` on V4.1 prints upstream's refusal. Compare the text with `git show upstream/main:ds4.c`.
- [x] 3.2 Server: delete the seven steering branches, the `ffn = 1` default and `directional_steering_scale_set`, with one `sf-ablate(steering)` marker; reduce the kv guard condition (D3). Verify each removed option exits 2 with "unknown option", and that `./ds4_test --server` passes.
- [x] 3.3 Eval: delete the three options and their config fields (D3). Verify `--dir-steering-file x` exits 2 and `--steering-profile` is still accepted (`--help` lists it).
- [x] 3.4 `ds4_help.c`: drop the removed options from each binary's help, keeping the CLI's three upstream lines and `--steering-profile`. Verify each binary's `--help` lists only the options it accepts.

## 4. Environment registry

- [x] 4.1 Remove the three lines from `ds4_env.def` and reword any description that names a removed option (D4). Verify `make env-check` passes, and that `DS4_ALLOW_V41_STEERING=1 ./sf-ds4-1flash --help` prints "is set but this build never reads it".

## 5. Docs

- [x] 5.1 Delete or rewrite the paragraphs found by D5's `git grep`, in `README.md`, `dir-steering/README.md`, `dir-steering/vectors/README.md`, `com-steering/make.md` (with the one-slot `make_profile.py` example) and `com-steering/spec.md`. Verify the `git grep` returns only `ds4_help.c` lines about the CLI's upstream options, if any.
- [x] 5.2 `AGENTS.md`: rewrite the Identity "Steering" row (profile only; the CLI's upstream file option reaches upstream's refusal; no opt-in) and note the deviation from the StarForge steering rule. Verify the row no longer names a removed option.
- [x] 5.3 `docs/upstream-prs.md` lines 40-42: state that the opt-in and raw options are gone and the site is reached through a profile. Verify the three lines name no removed option as current.

## 6. Verification

- [x] 6.1 `make test` (read the names of the tests that ran) and `make cpu`. Verify both pass.
- [x] 6.2 Repeat 1.1 on the branch. Verify both texts are byte-identical to the baseline and the stderr carries the same `residual steering` and `rank-2` lines.
- [ ] 6.3 `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout (unsteered). Verify it passes.
- [x] 6.4 `openspec validate 620-steering-profile-only --strict`. Verify it passes.

Notes from the implementation:
- 1.1/6.2: baseline built from the `610` tree (no CLI steering or prompt difference from main: the CLI's default `HIGH` reports 75 either way). Prompt "Explain in a short paragraph why the sky is blue during the day and red at sunset.", `--temp 0 -n 400 --ctx 4096 --ssd-streaming`, `--think` and `--nothink`: both texts byte-identical, and the `residual steering` and `rank-2` stderr lines identical.
- 2.1: the `401` check after the support check ("V4.1 steering applies only at --dir-steering-residual") was removed too: a nonzero FFN/attention scale needs a file, a file without a profile meets the support refusal, and a file with a profile meets the profile conflict, so it could no longer fire. The server's `parse_float_arg` lost its only callers and went with an `sf-ablate` line.
- 2.3: `ds41_steering_profile_open` sets `e->directional_steering_file2` and `_residual2_scale` for a second slot, and `cpu_load_directional_steering` loads it from there; the branch run printed the rank-2 line.
- 3.1: `--dir-steering-file /dev/null` on the branch's CLI printed upstream's refusal unchanged and exited 1.
- 3.4: `--help steering` now shows `--steering-profile` for the eval too, and the three upstream lines only for the CLI.
- 6.3: the parity oracle runs from the StarForge checkout against the child's main checkout, not this worktree; left open. The unsteered path is untouched by this change (option parsing and admission only).
