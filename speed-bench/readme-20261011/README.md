# README speed tables, 2026-10-11

Measured by `speed-bench/readme_bench.py` (`main` at `fa51b38`, ds4 at
`0aaea5a`); the protocol is in `speed-bench/README.md`, "README tables".

- `sweep/`: "Against ds4" and the second-drive sweep. `shapes/`: the
  second-drive harness shapes.
- `NN-<column>-<kind>.csv`: one run. `00-*` are the discarded warm-ups.
- `summary.md`: medians per column; `runs.json`: start temperature and
  thermal state, cool-down, peak chip, fan modes, thermal states and GPU
  clock of every measured run.
