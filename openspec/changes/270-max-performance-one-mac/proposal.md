# Proposal

## Why

Every figure in this repository is measured at `--ssd-streaming-cache-experts 82GB` (74.88 GiB dynamic, 8078 slots). That is the fixed measurement configuration and the value for normal use. No figure says how much more one Mac can give with every lever on at once.

The expert cache is the lever that does not fit inside the defaults. The engine caps an explicit cache at `floor(7/8 x recommendedMaxWorkingSetSize - context buffers)`. Today Metal recommends 107.52 GiB, so the cap is 86 GiB at a 32K context and 83 GiB at 256K. `225-mac-memory-evidence` gives the rest of the picture:
- **Decode stops gaining at about +770 slots** (about 89 GiB), from a replay of the selected expert ids.
- **Appends keep gaining** up to +1600 slots.
- **The file cache that a larger cache displaces serves 20-28% of today's miss reads.**

Raising `iogpu.wired_limit_mb` lifts the cap. The owner sets the frame:
- a 256K context allocated, which needs 10.38 GiB of context buffers;
- at least 18 GiB left to macOS and other apps;
- the copy on the second drive;
- `--boost`.

The cache plus the context buffers plus the 9.37 GiB of static weights must then stay at or under 110 GiB, so the largest admissible cache is 90 GiB.

This change finds the best value in that frame and writes a README section that tells how to run the ceiling test with it.

## What Changes

- **Harness, tool step.** `speed-bench/ab_bench.py` gets:
  - `--b-cache NGB`: B's cache flag; the window check follows the flag, and a `capped to` line stops the run;
  - `--ctx-alloc N`: the allocated context for both builds.

  The defaults stay `82GB` and 32768, so every existing invocation is unchanged.
- **Screening on the replay.** The `225` id dumps are replayed at the slot counts of 86, 88 and 90 GiB, for `decode` and `append`, before any run.
- **A/B per candidate.** 82 against 86, 88 and 90 GiB, measured on one tree with:
  - `--ctx-alloc 262144`;
  - the copy on both builds (`--env DS4_METAL_PREFILL_REPLICA=...`);
  - `--bitwise` and `--cache-policy-change`;
  - the working-set limit set once for the session by the owner (`sudo sysctl iogpu.wired_limit_mb=118000`).

  `--boost` stays off in every A/B (harness rule: one run's fans cool the next).
- **Memory check** of the chosen value: one timeline run with `vm_stat` and `footprint`. It must show no swapouts and no compression of the engine's pages, and the minimum available memory is reported.
- **Choice.** The value with the best pooled decode and append gains that passes the memory check. When two values are within each other's intervals, the smaller one wins, because it leaves more to macOS. The `sysctl` value for it is stated with its margin.
- **README section "Max performance on one Mac"**, named `max_performance_<GiB>` after the chosen value:
  - how to run the test: the `sysctl` and its reset, the copy, `--boost` with `fanboost`, the cache flag, `--ctx-alloc 262144`, and the bench sweep of the "Against ds4" table;
  - why those values;
  - a results table with the same rows as "Against ds4" plus an `82GB` column, **left empty**. The owner runs the test and fills it.
- No default changes: normal use and every harness measurement stay at `82GB` with the system limit.

## Capabilities

### New Capabilities
None (`skip_specs: true`): measurement, a harness option, and documentation.

### Modified Capabilities
None.

## Impact

- `speed-bench/ab_bench.py` (two options), `speed-bench/README.md` (their lines).
- `README.md` (the new section, and the `82GB` callouts that point to it).
- `speed-bench/perf-record.md` (a section with the replay, the A/B rows and the memory check).
- `docs/MacM5.md` (the working-set limit per cache and context).
- **Needs the external SSD mounted** (`/Volumes/ExtSSD`) for the copy, and the owner to run `sudo sysctl` before the A/B session and reset it after.
