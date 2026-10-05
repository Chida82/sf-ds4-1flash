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

DeepSeek V4.1 Flash Q2 against ds4 at the merge-base `0aaea5a`, 2026-10-05,
this child at `132-gpu-all-hit-continuation`: the sweep above with
`--ssd-streaming --ssd-streaming-cache-experts 82GB --ctx-start 2048
--ctx-max 32768 --step-mul 2 --gen-tokens 128`, two runs per build in the
order ds4, sf, sf, ds4. The CSVs are in
[speed-bench/v41-q2-vs-ds4-20261005](../speed-bench/v41-q2-vs-ds4-20261005)
and the table in the README's "Speed" section: prefill +27% to +58%, steady
decode +40% to +63%, the first token after a prefill 0.3-1.1 s against
2.1-3.0 s.

## What to compare next

