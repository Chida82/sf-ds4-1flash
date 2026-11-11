# Tasks

Rules for every task:
- Read `proposal.md` and `design.md` first. Line numbers there drift; find
  sites with `grep -n`.
- A test passes when its **output names the tests that ran**, not when the
  exit code is 0. Paste the count of pass lines into the task line.
- Never commit or push: staging is allowed, a commit needs the owner's request.
- Timing runs (group 5 and 6) need the owner to say the machine is free.
  Tests, model-backed ones included, do not.
- One model process at a time. After stopping one, wait 15 s for the lock.
- Never edit a tree while `ab_bench.py` is running on it: it rebuilds.
- When a task says STOP, stop, write what you found in the task line, and
  report. Do not try a workaround.
- After ticking a task, append its result to the same line (`Result: ...`).

## 1. Gate and setup

- [ ] 1.1 Gate: `grep -n '^## 780' speed-bench/perf-record.md` finds the section and it says `GO`. STOP if it is missing, `NO-GO` or `GREY`.
- [ ] 1.2 Worktree from `main` (which must contain `780`): `git worktree add .claude/worktrees/790 -b 790-v41-append-route-first-reads main`; a second, read-only one for the harness baseline: `git worktree add --detach .claude/worktrees/790-base main`. Verify: `git worktree list` shows both; `git config rerere.enabled` prints `true`.
- [ ] 1.3 Baseline in the work tree: `make`, `make test 2>&1 | tee "$OUT/test-before.txt"` (`OUT=$(mktemp -d)`). Verify: note the `env-check` count and the number of test lines here. STOP on any failure.

## 2. Read before writing (no edits in this group)

Each task ends with a sentence of evidence (`file:line` and the quoted line) in its `Result:`.

- [ ] 2.1 Seed: read `ds41_prefill_seed` and `ds4_gpu_stream_expert_cache_seed_experts_gpu_copy` (and the `_impl` it calls). Establish that an expert with `frequency == 0` is never copied from the bound buffers into the decode cache, even when fewer distinct experts were selected than the per-layer target. STOP if it can be: the design needs a guard first, ask.
- [ ] 2.2 Kernels, 32-511 rows: in `metal/moe.metal`, read `kernel_mul_mm_id_map0` and `kernel_mul_mm_id_mpp` and the pair-swiglu variant `kernel_mul_mm_id_iq2_xxs_pair_swiglu_f16`; in `ds4_metal.m` read which of them `ds4_gpu_routed_moe_batch_tensor` dispatches with `force_resident == true`. Establish that every weight address is computed from an expert id taken from the work list. STOP if any loop walks all experts' weights.
- [ ] 2.3 Kernels, 512+ rows: the same for the `_mpp_packed` kernels and `ds4_gpu_encode_moe_packed_rhs` (what does it pack: activations or weights?).
- [ ] 2.4 `ds41_route_batch` and `ds4_gpu_router_select_batch_tensor`: (a) do they end the command batch themselves (`ds4_gpu_end_commands` inside)? (b) with visual spans, does `b->selected` hold the ids of every row of the tile at `row * DS4_N_EXPERT_USED`? If (b) is no or unclear, selective mode is off for sweeps with visual spans (design D1): write which condition detects them.
- [ ] 2.5 Operands of `ds41_moe_batch`: list every tensor it reads or writes and confirm each is `g->batch` storage declared in `DS41_PREFILL_STORAGE`, plus the local `mid_f16` flag. STOP if a transient tensor crosses the planned split.
- [ ] 2.6 `ds41_prefill_expert_read_start` / `ds41_prefill_expert_read` / `_read_join`: what happens when no expert has `!ready[e]` (zero bytes to read)? Confirm no division by zero in the per-worker byte share and that join still returns true. If it is not handled, note the one-line guard needed for task 3.3.
- [ ] 2.7 `grep -n 'ds4_gpu_stream_prefill_copy_cached' *.c *.m *.h tests/*.c`: expect one call in `ds4.c`, one definition in `ds4_metal.m`, one declaration in `ds4_gpu.h`, two calls in `tests/test_deepseek41_graph.c`. Also check whether the CPU build (`make cpu`) needs a stub. STOP if the count differs and you cannot say why.

## 3. S1: selective delivery

- [ ] 3.1 Split `ds41_moe_batch` (design D2) into `ds41_moe_route_batch` and `ds41_moe_experts_batch`, `ds41_moe_batch` calling both. Verify: `make`; `make test` same lines as 1.3; and a text check that the `&&`/`||` grouping is unchanged (`git diff` of the function shows only the cut and the two new headers).
- [ ] 3.2 Model-backed bitwise check of the split alone, before anything else is built on it: `./tests/test_deepseek41_graph deepseek-v4.1-flash.gguf --prefill-parity speed-bench/promessi_sposi.txt` and `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_ROUTER_ONE`. Verify: both print their pass lines. (If the default GGUF symlink is broken, use the `gguf/` component the README names and say so.)
- [ ] 3.3 Mask (design D4): `wanted` parameter on `ds41_prefill_expert_read_start` and `ds4_gpu_stream_prefill_copy_cached`; `ready[e] = 1` for unwanted experts after the blit; existing call sites pass `NULL`; the guard of 2.6 if needed. Verify: `make`, `make test` unchanged.
- [ ] 3.4 Model-less test: extend the `--prefill-expert-stream` case in `tests/test_deepseek41_graph.c` (it already memcmp's `slot->tensor[j]` against the file) with a mask selecting a few experts, including two adjacent ones and the last one: wanted experts' bytes equal the file, `model_bytes` equals the wanted bytes only, and a mask of all zeros reads nothing and joins. Verify: `make test` prints the case's pass line; quote it.
- [ ] 3.5 Variables in `ds4_env.def`, sorted: `DS4_ENV(DS4_METAL_V41_SELECTIVE_SWEEP_MAX, tuning, unset, "SSD streaming, one box: largest one-tile prefill sweep (rows, 0-2047) that delivers only the experts its rows selected; 0 restores whole-layer delivery")` and `DS4_ENV(DS4_METAL_V41_SELECTIVE_SWEEP_POISON, test, any, "Overwrite the undelivered experts of a selective sweep's layer buffer, to prove no kernel reads them")`. Verify after 3.6: `make env-check` count is 1.3's plus 2.
- [ ] 3.6 The sweep (design D1, D3, D5, D6) in `ds41_graph_prefill_sweep`: `selective` computed per sweep with `#define DS41_SELECTIVE_SWEEP_MAX 1024` for now; skip the pre-loop read and the top-of-layer join/bind/read-ahead when selective; route, drain, build `wanted`, deliver, optional poison, bind, begin, experts. The non-selective path must be textually the old one. Verify: `make`, `make test` unchanged; `git diff --stat` touches only `ds4.c`, `ds4_metal.m`, `ds4_gpu.h`, `ds4_env.def`, `tests/test_deepseek41_graph.c`.
- [ ] 3.7 Smoke: bench `--frontiers 2048,2348 -n 16 --show-output` with `DS4_METAL_GRAPH_PREFILL_PROFILE=1`, once with the limit at `0` and once default. Verify: same generated tokens; the default run's 300-row sweep has 40 lines with `selected=`; its `model` GiB per layer is below the `0` run's. STOP if tokens differ.
- [ ] 3.8 Short review of S1's diff against `AGENT.md`: fix only what would make the step wrong or break a child rule.

## 4. Correctness

- [ ] 4.1 New mode `--selective-sweep PROMPT` in `tests/test_deepseek41_graph.c`, modelled on `check_decoder_suffix` (two sessions on one engine, `setenv`/`unsetenv` around each, comparison with `ds41_state_spans`, `history` and logits). Control: `DS4_METAL_V41_SELECTIVE_SWEEP_MAX=0`. Candidate: unset. Sequence on each: prefill 2048, append 300, compare; 64 `ds41_graph_step`, compare logits each step; append 512, compare; append 1000, compare; then a fresh session each: first prefill of 300, compare. Add the Makefile target `test-deepseek41-selective-sweep` next to `test-deepseek41-prefill-replica`. Verify: `make test-deepseek41-selective-sweep` prints one pass line per comparison point; quote the count.
- [ ] 4.2 Same mode, second pass in the same test: candidate with `DS4_METAL_V41_SELECTIVE_SWEEP_POISON=1`. Verify: all comparison points pass. STOP on any mismatch and report the first point and layer.
- [ ] 4.3 Prove the test can fail: temporarily make the mask drop one selected expert (a one-line local change), run 4.2, see it fail, revert. Verify: write the failing line here and `git diff` shows the hack gone.
- [ ] 4.4 Existing model-backed tests: `make test-deepseek41-metal`, `test-mxfp4-metal`, `test-engram`, `test-deepseek41-steering-session`; by hand `--decoder-suffix`, `--wide-prefill`, `--chunk-prefill` of `tests/test_deepseek41_graph`. Verify: pass lines for each; counts here.
- [ ] 4.5 If the second drive is mounted: `make test-deepseek41-prefill-replica REPLICA=<path>` and 4.1 once with `DS4_METAL_PREFILL_REPLICA=<path>`. If it is not mounted, say so here and tell the owner in the report; do not skip silently.
- [ ] 4.6 `make cpu` builds and `make test` passes after it (the CPU binaries have their own names).

## 5. The limit (timing: ask first)

- [ ] 5.1 Probe of design D7: bench `--frontiers 5000,5256,5640,6152,6920,7944,9480,11520 -n 256` (appends 256, 384, 512, 768, 1024, 1536, 2040) at `82GB`, with `DS4_METAL_V41_SELECTIVE_SWEEP_MAX=0` and `=2047`, order A B B A, two runs per mode, `fanboost` cool-down to the same temperature before each. Read each append's prefill seconds (the bench CSV column `ab_bench.py` reads for ttft). Verify: a table of 7 sizes x 4 runs here.
- [ ] 5.2 Set `DS41_SELECTIVE_SWEEP_MAX` by the rule of D7. STOP and record the idea as rejected (Rejected ideas row, section of 7.2) if 256 rows does not win by 3% in both pairs. Verify: `make test`, and 4.1 again (its 300/512/1000 appends must still cover both sides of the new limit: if the limit is below 1000, the 1000-row append now checks the untouched path, which is wanted).

## 6. Harness and parity (timing: ask first)

- [ ] 6.1 `python3 speed-bench/ab_bench.py --a .claude/worktrees/790-base --b . --kinds append,short,decode,cold-2500 --guards guard-decode --bitwise --budget 2700`, started with `caffeinate -i` and `nohup` so it survives the turn; no `--boost`. If pairs are dropped only for bytes read, rerun with `--cache-policy-change` added and say so. Verify: exit 0, the correctness gate passed, and the printed summary: `append +300` interval above zero, no headline wholly below zero. Paste the summary rows here.
- [ ] 6.2 If hits or misses differ between A and B at any frontier, explain it from the code before accepting (design, risk 3). STOP if you cannot.
- [ ] 6.3 If the run is inconclusive (interval of `append +300` across zero), repeat once with `--budget 3600 --kinds append,short` and pool with `ab_pool.py`. Still across zero: the step is not kept; report.
- [ ] 6.4 Final review pass over the whole region touched (`ds41_graph_prefill_sweep`, the two moe halves, `read_start`, `copy_cached`): delete what the change made dead, keep the idiom, output identical. If it changes runtime code, rerun 4.1, 4.2 and `make test`.
- [ ] 6.5 Parity oracle, from the StarForge checkout: `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`. Verify: token-identical on every prompt, speed within 2%. STOP if red.

## 7. Docs

- [ ] 7.1 `AGENTS.md`, the prefill bullets under "SSD streaming is not optional": one bullet for selective delivery (what, the limit, the variable, bitwise, the make target). Verify: it names `DS4_METAL_V41_SELECTIVE_SWEEP_MAX` and `790`.
- [ ] 7.2 `speed-bench/perf-record.md`: section `## 790 selective delivery in short sweeps (<date>)` before `## Adding a row`, with the D7 table, the harness summary and the row in the format of the 770 section's row. No names of who decided what.
- [ ] 7.3 `docs/upstream-prs.md`: on the `ee7e840` line and the #454 line, add that short one-tile sweeps deliver selected experts since `790` (their verdicts on long sweeps and on the selected-address path stand).
- [ ] 7.4 Report to the owner: results, diff stat, what was not run (second drive, anything skipped), and that nothing is committed. STOP here.

## Workflow follow-up

- One signed commit on `main` only when the owner asks; then remove the two worktrees.
- README speed tables and the `sfctl` serve worktree are updated only on the owner's request, after the merge.
- Archive the change after the merge.
