# Tasks

## 1. Measure the break-even

- [x] 1.1 `DS4_METAL_V41_WARM_APPEND_MIN` (tuning, `ds4_env.def`) sets the warm minimum where upstream's warm rule applies.
- [x] 1.2 Probe at `80GB`: appends of 64-1000 tokens after 2048 and 8192 tokens of context, token-major against sweep, ABBA, two runs per mode (design, Measurement).

## 2. Schedule

- [x] 2.1 `ds41_prefill_count`: under single-box SSD streaming the warm minimum is 256; TP keeps 1024.
- [x] 2.2 `tests/test_deepseek41_prefill.c`: dispatch table with the default and with `1024`; the medium-sweep switch case under both.
- [x] 2.3 `make test` passes.

## 3. Correctness

- [x] 3.1 `1024` against `main`: bench frontier and decode logits bitwise equal (2048, +448, +896).
- [x] 3.2 Default against `main`: same argmax after the appends; the change of tokens recorded.
- [x] 3.3 Model-backed tests: `test-deepseek41-metal` (132 pass lines), `test-mxfp4-metal`, `test-engram`, `test-deepseek41-steering-session`: PASS.
- [x] 3.4 `test-deepseek41-prefill-replica`: not run before archiving, the second drive was unmounted; run on `main` once it was back: PASS.

## 4. Harness

- [x] 4.1 A/B against `main` at `82GB`, kinds `append,decode,cold-5000,cold-10000`, `--output-change --cache-policy-change`: `append +300` gains, no headline loses beyond its noise. Result: append +300 +52.3%, +1500 +17.4%, the rest within noise (perf-record, 770).

## 5. Docs

- [x] 5.1 `AGENTS.md`, prefill schedule paragraph; `ds4_env.def` line.
- [x] 5.2 `speed-bench/perf-record.md` row and section.
- [x] 5.3 Harness kind `short` (512, +512 at 512, +512 at 1024; outside `all`) in the README shapes table, and `readme_bench.py --columns` for partial sessions.
