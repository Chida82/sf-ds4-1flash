# README speed tables, 2026-11-07, 80GB

Measured by `speed-bench/readme_bench.py` (`main` at `6898b39`, ds4 at
`b3f5018`, GGUF `1017`), every column at `--ssd-streaming-cache-experts
80GB`. The protocol is in `speed-bench/README.md`, "README tables".

- `sweep/` holds "Against ds4", the second-drive sweep and
  `max_performance_80`.
- `shapes/` holds the second-drive harness shapes.
- `NN-<column>-<kind>.csv` is one run. The `00-*` files are the discarded
  warm-ups.
- `summary.md` gives the medians per column.
- `runs.json` records, for every measured run:
  - start temperature and thermal state, and the cool-down;
  - peak chip temperature and fan modes;
  - thermal states and GPU clock.

The earlier session of the same day, at `82GB` before `760`, is in
`../readme-20261107`.
