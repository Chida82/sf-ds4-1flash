# Proposal

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
- **S4, defaults.** The cap and the confidence threshold are swept on `decode-code` and `decode` together. The pair with the best code gain that keeps prose within the rule becomes the default.
- **S5, a smaller drafter.** Only if `310`/`320` show that the drafter's memory costs more decode than its precision gives:
  - our own conversion of the official `mtp.*` weights with Q2-class experts, about 4 GiB (estimated);
  - its acceptance re-measured against MXFP4 on the four kinds;
  - its `download.sh` component pointing to a file the owner publishes.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `dspark-drafting`: the automatic cache budget leaves room for the drafter; the support file may carry Q2-class expert types (S5 only).

## Impact

- `ds4.c`: the budget, the scheduler, and the loader's accepted types (S5).
- The miss path in `ds4.c` and `ds4_metal.m` (S2).
- `speed-bench/perf-record.md`, `README.md` (the gains table), `download.sh` (S5).
- S5 needs the owner for the shard download (about 7.4 GiB), a temporary Python environment in a `mktemp` directory, and publishing the converted file.
