# README speed tables, 2026-11-07, steady state

Measured by `speed-bench/readme_bench.py` (`main` at `4353306`, ds4 at
`b3f5018`, GGUF `1017`), every column at `--ssd-streaming-cache-experts
80GB`. The protocol is in `speed-bench/README.md`, "README tables": each
build's block drops the GGUF and the copy from the page cache once, runs two
discarded warm-ups, then its measured runs back to back, five per column in
the sweep and three in the shapes.

- `sweep/` holds "Against ds4", the second-drive sweep and
  `max_performance_80`.
- `shapes/` holds the second-drive harness shapes, `short` included.
- `NN-<column>-<kind>.csv` is one run. The `00-*` files are the discarded
  warm-ups.
- `summary.md` gives the medians per column.
- `runs.json` records, for every measured run:
  - start temperature and thermal state, and the cool-down;
  - the GiB of the GGUF and of the copy in the page cache at its start;
  - peak chip temperature and fan modes;
  - thermal states and GPU clock.

At steady state ds4's runs started with 33.6-35.0 GiB of the GGUF in the
page cache and sf's sweeps with 27.4-30.4 GiB. Every measured run started and
stayed at thermal pressure Nominal.

The earlier sessions of the same day are in `../readme-20261107-80gb` (`80GB`,
`6898b39`, three runs after one warm-up per block) and `../readme-20261107`
(`82GB`, before `760`).
