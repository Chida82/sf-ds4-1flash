# README speed tables, 2026-11-07

Measured by `speed-bench/readme_bench.py` (`main` at `5938e97` with change
`750`, ds4 at `b3f5018`, GGUF `1017`). The protocol is in
`speed-bench/README.md`, "README tables".

- `sweep/` holds "Against ds4", the second-drive sweep and
  `max_performance_82`. The sweep added two columns: `sf 80GB` and
  `max_performance_82`.
- `shapes/` holds the second-drive harness shapes.
- `NN-<column>-<kind>.csv` is one run. The `00-*` files are the discarded
  warm-ups.
- `summary.md` gives the medians per column.
- `runs.json` records, for every measured run:
  - start temperature and thermal state, and the cool-down;
  - peak chip temperature and fan modes;
  - thermal states and GPU clock.
