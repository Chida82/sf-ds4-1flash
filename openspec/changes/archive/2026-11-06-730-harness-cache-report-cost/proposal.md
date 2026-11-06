# Proposal

## Why

`speed-bench/ab_bench.py` runs every bench with `--cache-stats`, which prints
`ds4_engine_memory_report` after each frontier; the harness reads the expert
cache counters from that report. During the `b3f5018` sync one bench run
without `--cache-stats` gave a first decode token after a sweep of 92-140 ms,
against 166-217 ms in every run with it. That suggested the report slows the
next first token by 60-100 ms.

The code does not support it: the report reads counters and calls `task_info`
once, and it runs after a frontier's CSV row, before the next frontier's
prefill, not between a prefill and its first token. One run is also inside the
±20-40 ms noise of this measure. The question is open, and it matters for the
absolute first-token figures in `perf-record.md` (A and B both pay it, so the
A/B gains are unaffected).

This change answers it with a measurement and changes the harness only if a
cost is found.

## What Changes

- An `ab_bench.py` option that drops `--cache-stats` from B's runs, for an A/A
  measurement of its cost. The cache-state check needs B's counters, so the
  option implies a declared cache-policy change (the pairs are kept, with a
  note).
- One A/A run on the sync tree: `--kinds cold-2500,append,decode`, B without
  the report.
- If B's first token after a sweep is lower with an interval wholly below
  zero: move the report out of the timed sequence (print the counters at the
  end, or read them without the memory report), and note in `perf-record.md`
  which first-token figures carried the cost. Otherwise: record the result and
  remove the option.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `perf-harness`: an A/A option that runs B without the per-frontier cache
  report.

## Impact

- Tooling: `speed-bench/ab_bench.py`, `speed-bench/README.md`; possibly
  `ds4_bench.c` (`--cache-stats` output) if a cost is found.
- Docs: `speed-bench/perf-record.md` (the result; correction of the absolute
  first-token figures if needed).
- No engine code, no output change.
