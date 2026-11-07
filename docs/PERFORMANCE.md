# Performance and Benchmarking

[README](../README.md)

> **Hardware.** Every performance number in this repository was measured on
> one machine: an Apple **M5 Max with 128 GB** of unified memory, with the
> DeepSeek V4.1 Flash Q2 GGUF streamed from its internal SSD. Other Macs will
> give different absolute numbers.

Compare the same checkpoint, quantization, context, and sampling settings.
Record the commit and whether weights were resident, streamed, or distributed.
Keep other GPU workloads idle and repeat in alternating order: one favorable
run is not a speed result.

## Context sweeps

`sf-ds4-1flash-bench` measures prefill and generation at successive context frontiers:

```sh
./sf-ds4-1flash-bench -m deepseek-v4.1-flash.gguf \
  --prompt-file speed-bench/promessi_sposi.txt \
  --ctx-start 2048 --ctx-max 65536 --step-incr 2048 --gen-tokens 128
```

Each prefill number measures the newly added interval. Generation uses a fixed
greedy, non-EOS probe. The benchmark normally restores a memory snapshot after
each probe; network TP/pipeline runs and snapshots beyond its memory limit use
prefix replay instead. Do not interpret replay time as continued-prefill speed.

Use `--step-mul F` for exponential context spacing. Output is CSV, including
prefill throughput, generation throughput, and snapshot size when available.
The prompt is the cleaned public-domain *I Promessi Sposi* text in
[speed-bench](../speed-bench/README.md).

## Before/after verdicts

A change is judged with `speed-bench/ab_bench.py`, which runs two build trees
on the same GGUF under SSD streaming with a fixed expert cache, in A B B A
quads gated on identical tokens, and prints per metric the median gain with a
bootstrap 95% interval. The kinds, the cache rules, the exit statuses and the
measured noise floor are in the "A/B harness" section of
[speed-bench/README.md](../speed-bench/README.md); where the work started and
where it has got to is in [speed-bench/perf-record.md](../speed-bench/perf-record.md).
A single sweep with the command above is a picture of one build, not a verdict.

## Recorded baselines

DeepSeek V4.1 Flash Q2 (`1017`) against ds4 at the merge-base `b3f5018`, 2026-11-07,
this child at `main` `4353306`: the sweep above with
`--ssd-streaming --ssd-streaming-cache-experts 80GB --ctx-start 2048
--ctx-max 32768 --step-mul 2 --gen-tokens 128`, measured by
`speed-bench/readme_bench.py` at steady state (five runs per column from the
same cool chip, after two discarded warm-ups per build; protocol in
`speed-bench/README.md`, "README tables"), GGUF on the internal drive only.
The CSVs are in
[speed-bench/readme-20261107-steady](../speed-bench/readme-20261107-steady)
and the table in the README's "Speed" section:
- prefill +46% on the first 2048 tokens and +41% to +113% after them;
- steady decode +35% to +72%;
- the first token after a prefill 0.18-0.22 s against 2.3-3.3 s.

With `--boost` (fans at their maximum through fanboost) the same sweep gains
+7% on the prefill to 16384, +5% on the one to 32768 and under 1% on steady
decode. The same session measured the second-drive copy, short chat turns
included (README, "A second drive"), and `max_performance_80`.

Chat-sized turns against ds4 (`readme_bench.py short`, 2026-11-08, `main`
`ebf255b`, 512 to 1536 tokens in steps of 512, three runs each,
[speed-bench/readme-20261108-short](../speed-bench/readme-20261108-short)):
a 512-token append takes 6.7-6.9 s against ds4's 20.0-20.4 s, which runs it
token by token; the first 512-token prompt 12.0 s against 15.0 s.

Earlier baselines:
- 2026-11-07, `6898b39` at `80GB`, three runs after one warm-up per build:
  [speed-bench/readme-20261107-80gb](../speed-bench/readme-20261107-80gb).
- 2026-11-07, `5938e97` with change `750` at `82GB` (static weights still
  pageable), against ds4 at `b3f5018`:
  [speed-bench/readme-20261107](../speed-bench/readme-20261107).
- 2026-10-11, `fa51b38` against ds4 at `0aaea5a`:
  [speed-bench/readme-20261011](../speed-bench/readme-20261011).
- The 2026-10-10 sweep (two runs per build, no cool-down):
  [speed-bench/v41-q2-vs-ds4-20261010](../speed-bench/v41-q2-vs-ds4-20261010).

## What to compare next

