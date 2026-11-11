# Tasks

Rules for every task:
- Read `design.md` first. Line numbers there drift; find sites with `grep -n`.
- A test passes when its **output names the tests that ran**, not when the
  exit code is 0. Paste the count of pass lines into the task line when you
  tick it.
- Never commit or push: staging is allowed, a commit needs the owner's request.
- When a task says STOP, stop, write what you found in the task line, and
  report. Do not try a workaround.
- After ticking a task, append its result to the same line (`Result: ...`).

## 1. Setup

- [ ] 1.1 Work in a worktree, never on `main`: `git worktree add .claude/worktrees/780 -b 780-v41-append-selected-experts-evidence main`, enter it, and check `grep -c 'claude/worktrees' .git/info/exclude` in the main checkout is at least 1 and `git config rerere.enabled` prints `true`. Verify: `git branch --show-current` prints the branch name.
- [ ] 1.2 Baseline: `make` then `make test 2>&1 | tee "$OUT/test-before.txt"` with `OUT=$(mktemp -d)`. Verify: the first line of the test output is `env-check: <N> DS4_* variables classified`; write `N` and the number of test lines here. STOP if anything fails before your first edit.
- [ ] 1.3 Confirm the anchors of the design exist, each with one `grep -n`: `ds41_graph_prefill_sweep`, `ds41_prefill_seed(` (definition and its one call), `expert_slots[il & 1u]`, `explicit_experts`, `DS4_METAL_GRAPH_PREFILL_PROFILE` in `ds4.c`. Verify: every grep has a hit. STOP if `ds41_prefill_seed` is called from more than one place or `ready` is no longer a field of `ds41_prefill_expert_slot`: the design no longer matches the code.

## 2. Probe

- [ ] 2.1 Add `ds41_prefill_selected_stats` to `ds4.c` right above `ds41_prefill_seed`, exactly as design D2 (signature, id range check, `seen[]`, three counters). No GPU call, no global. Verify: `make` builds with no new warning.
- [ ] 2.2 Model-less test in `tests/test_deepseek41_prefill.c` (open it first and follow how it reaches `ds4.c` statics and how it reports a pass line). Cases: (a) 2 rows selecting ids `{0,1,2,3,4,5}` and `{0,1,2,3,4,6}`, `ready[]` all 0 except `ready[0] = ready[6] = 1`: expect `distinct == 7`, `distinct_uncached == 5`, `uncached == DS4_N_EXPERT - 2`; (b) an id of `-1` and an id of `DS4_N_EXPERT`: expect `false`; (c) all `ready` set: `distinct_uncached == 0`, `uncached == 0`. Verify: `make test` prints the new test's pass line; quote it here.
- [ ] 2.3 Read the variable in `ds41_graph_prefill_sweep` next to the `profile` variable, the same way that line reads `DS4_METAL_GRAPH_PREFILL_PROFILE`, and add the `ds4_env.def` line of design D3 in sorted position. Verify: `make env-check` prints `env-check: <N+1> DS4_* variables classified`.
- [ ] 2.4 Call site, design D1: right before the `ds41_prefill_seed` call, under `stats && explicit_experts && off == 0` (inside the existing last-tile condition), read `ds4_gpu_tensor_contents(g->batch.selected)`, call the helper with `expert_slots[il & 1u].ready`, and `fprintf(stderr, ...)` the exact line of D2. A `false` return prints nothing. Verify: `git diff --stat` shows only `ds4.c`, `ds4_env.def`, `tests/test_deepseek41_prefill.c`; `make test` output has the same test lines as 1.2 plus the new one.
- [ ] 2.5 Short review of the diff against `AGENT.md`: comment only the why, no dead code, names in the file's idiom. Verify: `git diff | grep -c '^+'` is under 90 including the test.

## 3. Sanity on the model

- [ ] 3.1 One short run: the bench command of design D4 with `--frontiers 2048,2348 -n 16`, `<FILE>` the novel. Verify in `$OUT/sanity.err`: exactly 80 `V4.1 prefill selected` lines (40 with `rows=2048`, 40 with `rows=300`), layers 0..39 each once per sweep, and on every line `distinct <= 384`, `distinct <= rows*6`, `distinct_uncached <= distinct`, `distinct_uncached <= uncached`. STOP if a count is wrong.
- [ ] 3.2 Cross-check with the profile: for five layers of the 300-row sweep, `uncached * 9.49 MiB` must equal the `model + replica` GiB of the `V4.1 prefill layer=<il> experts from RAM ...` line within 2%. Verify: write the five pairs here. STOP if they disagree: `ready[]` is not what the design says.
- [ ] 3.3 Same command without the two variables. Verify: `grep -c 'V4.1 prefill selected' ` is 0, and the generated tokens (`--show-output`) and the `hits=`/`misses=` of every `streaming expert cache` line equal those of 3.1.

## 4. Counting runs

- [ ] 4.1 Build `$OUT/mixed.txt` (design D4). Verify: `head -c 200` shows Italian and `tail -c 200` shows C.
- [ ] 4.2 Run R1, R2, R3, R4 of design D4, one at a time, each to its own `.err`/`.out`. These are counting runs: no quiet machine is needed, but no other model process may run. Verify per run: exit code 0, and the D5 summary prints four lines (`rows=256`, `300`, `512`, `1000`) each with `layers=40`. If R2's first frontier also prints `rows=2048`, keep that line as a cold reference.
- [ ] 4.3 Run R1 a second time. Verify: each `r_disk` and `r_all` differs from the first R1 by less than 0.05. If not, run it a third time and report all three; do not average.

## 5. Verdict and record

- [ ] 5.1 Apply the gate of design D6 to the `rows=300` and `rows=256` lines. Verify: write here `GO`, `NO-GO` or `GREY` and the eight numbers that decided it.
- [ ] 5.2 `speed-bench/perf-record.md`: new section before `## Adding a row`, titled `## 780 experts a short append selects (<date>)`, with the commands, a table of the D5 lines of all runs (run, rows, distinct/layer, uncached/layer, distinct_uncached/layer, r_all, r_disk), the gate and the verdict. No names of who decided what. Verify: the section's table has 16 rows or more.
- [ ] 5.3 Fix the uncounted statements with the measured figure: the parenthesis "128 rows touch most of its experts" in the Rejected ideas `530` row and "128 rows touch most of a layer's experts" in the 530 section. Replace each with what R2's cold `rows=2048` line and the `rows=256` lines show, citing this section. Verify: `grep -n 'touch most' speed-bench/perf-record.md` returns nothing, or only lines that now carry a number.
- [ ] 5.4 Only if `NO-GO`: add a row to the Rejected ideas table (`| Idea | Why it does not help here | Section |`): idea "Route-first delivery of only the selected experts in 256-1000-row sweeps", the measured `r_disk`, section name of 5.2; and write `Closed by 780, no code` at the top of `openspec/changes/790-v41-append-route-first-reads/proposal.md`. Verify: the row is the last of the table.
- [ ] 5.5 Only if `GO`: replace the estimates in `790`'s `proposal.md` (Why) with the measured `r_all` and `r_disk` at 300, 512 and 1000 rows. Verify: `grep -n 'estimate' openspec/changes/790-v41-append-route-first-reads/proposal.md` shows no stale estimate.
- [ ] 5.6 Report to the owner: the verdict, the table, the diff stat, and that nothing is committed. STOP here.

## Workflow follow-up

- Commit on the branch and merge to `main` as one signed commit only when the owner asks.
- Archive the change after the merge.
