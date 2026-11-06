# Tasks

## 1. Option

- [x] 1.1 `ab_bench.py`: an option dropping `--cache-stats` from B's bench command (`bench_cmd`), implying `--cache-policy-change`, with B's hit rates printed as unavailable; `speed-bench/README.md` documents it
- [x] 1.2 Check the option on a dry invocation (A's command has `--cache-stats`, B's does not)

## 2. Measure

- [x] 2.1 A/A on the sync tree: `--kinds cold-2500,append,decode` with the option
- [x] 2.2 Record the first-token gains and intervals in `speed-bench/perf-record.md`

## 3. Decide

- [x] 3.1 (not needed: no interval below zero) Interval wholly below zero for B's first token: move the report out of the timed sequence (counters at the end of the run, or read without the memory report) and note which absolute first-token figures in perf-record carried the cost
- [x] 3.2 Otherwise: remove the option again and close with the measured figure
