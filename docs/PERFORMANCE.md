# Performance and Benchmarking

[README](../README.md)

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

## Recorded baselines

sf-ablate(ds4): none yet. The sweeps that used to fill this section were
measured on DeepSeek V4 Flash and V4 PRO, which this fork does not run, and
were deleted rather than relabelled: a throughput number carried over from
another model is worse than an empty section. Record a DeepSeek V4.1 Flash
sweep with the command above and add the CSV under `speed-bench/`.

## What to compare next

