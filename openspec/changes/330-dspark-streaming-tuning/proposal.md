# Proposal

> **Status 2026-10-28: stopped by `310`.** One verify row costs about 0.6 of a decode token under streaming (bitwise configuration); main projects under 1x on code. Reopen only if a verify row can cost at most 0.3 of a decode token on main (`310` "Margin verdict", `speed-bench/perf-record.md` "DSpark verify cost under streaming").

## Why

`320` ports #1073's drafter as written, with the verify rows on the streaming cache. Four things are specific to streaming, and #1073, being resident only, never had to solve them:
- **The automatic expert-cache budget** does not know about the drafter's resident memory.
- **A verify cycle can miss more experts than one decode token.** The cycle needs the union of k+1 rows' experts.
- **The drafter's precision.** It is MXFP4, 7.42 GiB, about 800 slots of cache.
- **Back-off.** It is tuned on resident timings, where a losing cycle costs less.

This change takes them one at a time, each judged as a step, in the order `310` and `320`'s measurements rank them.

## What Changes

Each step is kept or dropped by the config's rule, A = the previous step, B = the step, with `--dspark` on both and the harness kinds `decode-code` and `decode`:

- **S1, budget.** With `--dspark` and no explicit cache flag, the automatic budget subtracts the drafter's resident bytes from what it gives the cache. Its startup line says so. An explicit flag keeps meaning the cache, as today. This is a correctness of memory, not a speed claim: it is checked with `310`'s memory timeline under the automatic budget.
- **S2, parallel union reads.** Only if `320`'s section shows a verify cycle's miss time growing with the union's size: the union's misses for a layer go out together, on the reader pool and both drives (the `145`/`260` split), rather than one after another.
  - Route-prediction prefetch is not proposed. `170` closed it: a guess costs about 0.3 ms per row, more than the 0.25 ms it hides, and that ratio does not change per row.
- **S3, back-off.** The skip schedule becomes #1168's (an `idea`, not a port, because #1168 is written for V4 Flash):
  - consecutive rejected proposals double the pause, from 2 up to 64 cycles;
  - the first miss is not punished;
  - accepted cycles earn credit that absorbs isolated misses;
  - any accepted draft restores drafting.

  On M5 Max, V4 Flash, it measured reasoning prose -0.1% and code +19.5%. This step is taken first if `320` left prose under `310`'s rule.
- **S4, draft length: expected cost against threshold and cap.** Two arms are run on `decode-code` and `decode` together:
  - **Threshold and cap,** #1073's rule. The pair is swept, and the one with the best code gain that keeps prose within the rule is the arm.
  - **Expected cost,** DeepInfer's rule (`MTPVarlen::schedule`) for one request. Each cycle drafts `k* = argmax_k (1 + sum_{j<=k} P_j) / t(k)`, with k = 0 allowed (a plain step). `P_j` is the running product of the block's per-position confidences. t(k) is `310`'s c(k) curve, scaled by the plain token time the session already measures and corrected at runtime by a windowed median of measured cycle times. That correction absorbs the variable cost of expert misses under streaming, which a fixed threshold cannot see.

  The expected-cost arm becomes the default if it beats the threshold arm by the keep rule. It then replaces the threshold sweep. `--dspark-confidence X` keeps working and selects the threshold rule. The rule also absorbs part of S3's job: a cycle it prices as losing verifies nothing, so back-off only has to save the drafter's own time. `310` D7b's replay sets which arm starts as the baseline and whether the second arm runs at all.
- **S5, a smaller drafter.** Only if `310`/`320` show that the drafter's memory costs more decode than its precision gives:
  - our own conversion of the official `mtp.*` weights with Q2-class experts, about 4 GiB (estimated);
  - its acceptance re-measured against MXFP4 on the four kinds;
  - its `download.sh` component pointing to a file the owner publishes.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `dspark-drafting`: the automatic cache budget leaves room for the drafter; the draft length is chosen by expected cost unless a threshold is given (S4, only if kept); the support file may carry Q2-class expert types (S5 only).

## Impact

- `ds4.c`: the budget, the scheduler (back-off and the S4 draft-length rule), and the loader's accepted types (S5).
- `ds4_env.def`: S4's switches.
- `docs/upstream-prs.md`: if S4 keeps the rule, a row records DeepInfer's `MTPVarlen::schedule` as the idea's source.
- The miss path in `ds4.c` and `ds4_metal.m` (S2).
- `speed-bench/perf-record.md`, `README.md` (the gains table), `download.sh` (S5).
- S5 needs the owner for the shard download (about 7.4 GiB), a temporary Python environment in a `mktemp` directory, and publishing the converted file.
