# Tasks

## 1. Branch

- [x] 1.1 Create the branch.
  - Run `git config rerere.enabled true`, then
    `git switch -c fix/15-shared-expert-guard main` (design D6).
  - Verify: `git branch --show-current` prints the branch, and
    `git status --short` is empty.

## 2. The fix

- [x] 2.1 In `ds41_moe_partial` (`ds4.c` ~24087), replace the one-line guard
  with the form in design D1, and add the `sf-ablate(cuda)` marker of design
  D2 on the line above it.
  - Verify: diff the function against upstream's with
    `diff <(sed -n '/^static bool ds41_moe_partial/,/^}/p' ds4.c) <(git show upstream/main:ds4.c | sed -n '/^static bool ds41_moe_partial/,/^}/p')`.
    The only differences should be:
    - the marker line;
    - the missing `bool shared_queued` declaration and its `#if` block;
    - the missing `!shared_queued &&` token;
    - the missing `#ifndef __APPLE__` routed branch;
    - the missing CUDA `ds4_gpu_dsv41_shared_join` block after the routed call (also covered by the marker).
- [x] 2.2 Delete the three fold constants (design D3):
  - `!false &&` in `fuse_attn_out_hc` (~17161);
  - `!false &&` in `fuse_shared_down_hc` (~17625);
  - `|| false` in `split_commands` (~22665).
  - Verify: `grep -nE '!false|!true|\(false *(&&|\|\|)|(&&|\|\|) *(false|true)\b' ds4.c ds4_metal.m`
    prints nothing.
- [x] 2.3 Add the lesson paragraph to `AGENTS.md`, in "Removing code
  (ablation)" (design D5).
  - Verify: `grep -n 'ds41_moe_partial' AGENTS.md` shows the new paragraph.

## 3. Checks (no model)

- [x] 3.1 Build.
  - Run `make -j8`.
  - Verify: no new warnings against `main`'s build, compared from both build
    logs.
- [x] 3.2 Run `make test`.
  - Verify: `grep -c '^test:' Makefile` prints 1, and the output names the
    suites that ran. The exit code alone is not the check.
- [x] 3.3 Run `make test-deepseek41-metal`.
  - Verify: it ends with its pass line, and no case reports a mismatch.

## 4. Parity (loads the model: ask the owner first)

- [x] 4.1 Ask the owner for the go-ahead to load the model. Do not start
  until they say yes.
- [x] 4.2 From the StarForge checkout, run
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`.
  Run it alone, with no build or test beside it.
  - Verify: `PARITY OK`, meaning token-identical output and speed within ±2%.
  - If speed alone trips, re-run once after a cool-down. If tokens differ,
    stop and report: design D4 says they cannot.

## 5. Review and close

- [x] 5.1 Read the final diff against `main` in full
  (`git diff main -- ds4.c AGENTS.md`).
  - It holds only the guard, the marker, the three constants and the
    paragraph.
  - Every hunk matches design D1-D5.
  - Verify: the diff stat lists only `ds4.c` and `AGENTS.md`.
- [x] 5.2 Run `openspec validate 15-shared-expert-guard`.
  - Verify: it passes.
- [x] 5.3 Only once the owner asks for the commit, make one commit on the
  branch (design D6):
  `fix(v41): restore the shared-expert guard grouping lost in the deep prune`.
  - Verify: `git show --stat HEAD` lists `ds4.c`, `AGENTS.md` and this
    change's `openspec/` files.
