# Tasks

## 1. Harness options

- [ ] 1.1 `speed-bench/ab_bench.py`: `--b-cache NGB` (B's cache flag, B's window `N - 7.12` ± 0.5 GiB) and `--ctx-alloc N` (both builds, the context-line check follows it); a `capped to` line in either build's stderr stops the run with exit 2; defaults reproduce today's invocation. Document both in `speed-bench/README.md`. Verify an A/A run with `--b-cache 82GB --kinds decode` is bitwise with no metric below zero, and that `--b-cache 90GB` without the raised limit stops on `capped to`.

## 2. Screening

- [ ] 2.1 Replay the `225` decode and append id dumps at the slot counts of 86, 88 and 90 GiB (from the loader's slot size; regenerate the dumps with the `225` scratch build if they are gone). Verify 8078 slots still reproduce 3.91 / 4.05 miss layers per token; record the table in `perf-record.md` and drop from 3.x a candidate that replays identical to the next smaller one on both kinds.

## 3. Measurement (owner runs `sudo sysctl iogpu.wired_limit_mb=118000` first; external SSD mounted)

- [ ] 3.1 Read back Metal's recommended working set and the cap at `--ctx-alloc 262144` (engine estimate). Verify 90 GiB is not capped; if it is, compute the new W with D2's formula and ask the owner for it.
- [ ] 3.2 Harness A/B per remaining candidate: A `82GB`, B `--b-cache <C>GB`, `--kinds decode,append --guards guard-16896,guard-decode --bitwise --cache-policy-change --ctx-alloc 262144 --env DS4_METAL_PREFILL_REPLICA=/Volumes/ExtSSD/sf-ds4-1flash/DeepSeek-V4.1-Flash-Q2.gguf`. Verify each run with the keep rule's arithmetic (pooled CIs); repeat an inconclusive one once with a longer budget on decode; record the rows.
- [ ] 3.3 Memory timeline of the chosen value (D4) at `--ctx-alloc 262144` with the copy. Verify zero swapouts and no compressed engine pages; record the minimum available memory and the file-backed pages next to `225`'s.
- [ ] 3.4 Choose C by D5 and W by D2; ask the owner to reset `sudo sysctl iogpu.wired_limit_mb=0`. Verify the choice and its reason are in the `perf-record.md` section.

## 4. Documentation

- [ ] 4.1 Write the README section "Max performance on one Mac" by D6: test `max_performance_<C>`, the commands with the chosen C and W and the reset, preconditions, the reason for each value, the `capped to` check, and the results table (rows of "Against ds4", columns `82GB` and `max_performance_<C>`) with every cell empty; replace the provisional draft in the working tree and point the `82GB` callout under "Speed" to it. Verify the command is copy-paste correct: one short smoke run of it with `--ctx-max 2048 --gen-tokens 16` under the raised limit shows no `capped to` line and the cache line it predicts (the smoke figures are not written to the table).
- [ ] 4.2 `docs/MacM5.md`: the working-set limit per cache and context (the D2 formula and the 32K/256K/1M rows). Verify the numbers match `perf-record.md`.

## 5. Integration

- [ ] 5.1 `make test`; review the harness diff against `AGENT.md`; `openspec validate 270-max-performance-one-mac --strict`. No commit or push without a request.
