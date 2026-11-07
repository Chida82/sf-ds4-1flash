# README chat-turn table, 2026-11-08

Measured by `speed-bench/readme_bench.py short` (`main` at `ebf255b`, same
engine as `4353306`; ds4 at `b3f5018`, GGUF `1017`), both builds at
`--ssd-streaming-cache-experts 80GB`: upstream's bench from 512 to 1536 tokens
in steps of 512, 16 generated tokens, a 32K context allocated. The protocol is
in `speed-bench/README.md`, "README tables": each build's block drops the GGUF
from the page cache once, runs two discarded warm-ups, then three measured
runs back to back.

- `NN-<column>-short.csv` is one run. The `00-*` files are the discarded
  warm-ups.
- `summary.md` gives the medians per column.
- `runs.json` records, for every measured run, the cool-down, start and peak
  temperature, thermal states, GPU clock and the GiB of the GGUF in the page
  cache at its start.

At steady state ds4's runs started with 39.7-40.2 GiB of the GGUF in the page
cache and sf's with 11.65 GiB: sf reads experts uncached, so a session of
short turns leaves only the static weights there. Every run started and
stayed at thermal pressure Nominal.
