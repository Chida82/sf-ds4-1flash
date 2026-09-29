## Benchmarking

Here we collect prefill and generation speed obtained with different hardware.

sf-ablate(ds4): the CSV and SVG baselines that used to live here were measured
on DeepSeek V4 Flash and V4 PRO, which this fork does not run. They were
deleted rather than relabelled -- a number carried over from another model is
worse than no number. Contribute a DeepSeek V4.1 Flash sweep from your own
hardware with the command below.

Run `sf-ds4-1flash-bench` as:

```
./sf-ds4-1flash-bench \
  -m deepseek-v4.1-flash.gguf \
  --prompt-file speed-bench/promessi_sposi.txt \
  --ctx-start 2048 \
  --ctx-max 65536 \
  --step-incr 2048 \
  --gen-tokens 128
```

Provide PR including your numbers if your hardware was not already tested.
Call the benchmark csv file something like `m3_max.csv` or alike, so that
it is clear what hardware was used for the benchmark.

To generate an SVG graph from a CSV file:

```
python3 speed-bench/plot_speed.py speed-bench/m3_max.csv --title "M3 Max t/s"
```

The script uses only the Python standard library. By default it writes a file
next to the CSV using the `_ts.svg` suffix, such as `speed-bench/m3_max_ts.svg`.

### A/B harness

`ab_bench.py` compares two build trees of this child on one GGUF under SSD
streaming and prints a verdict that fits one screen:

```sh
git worktree add ../sf-ds4-1flash-base main          # A: the baseline, once
python3 speed-bench/ab_bench.py --a ../sf-ds4-1flash-base --b . --kinds decode --guards guard-decode
```

Pass trees, not binaries: the kernels are read from `metal/` in the working
directory when the process starts, so each build runs from its own tree. The
harness runs `make sf-ds4-1flash-bench` in both trees first. `--a` and `--b`
may be the same tree; that A/A run measures the noise floor.

Every bench process runs with `--ssd-streaming --ssd-streaming-cache-experts
82GB --ctx-alloc 32768`: the loader takes the 7.12 GiB prefill headroom from
the 82 GiB and turns the rest into expert slots. The harness reads each run's
`dynamic cache` line and refuses (exit 2, line quoted) when the dynamic cache
is outside 74.5-75.5 GiB or the slot count differs between runs, so A and B
always hold the same cache. Cache state itself is also watched: every timed
run records its expert-cache hits, misses, bytes read and read time per
frontier (the bench's `--cache-stats` report), and a pair whose hits or misses
differ by more than `--cache-tolerance` (0.01 of the lookups) or whose bytes
read differ by more than 5% is dropped with the reason, so a code change and a
cache-state change are never confused. A change that alters eviction or
preload passes `--cache-policy-change`: the pair is kept and the summary shows
both hit rates.

One invocation:

1. **Preflight.** It refuses (exit 2), naming the reason, unless the machine is
   on AC power, the thermal state is Nominal, the GPU is below `--max-gpu-temp`
   (60 C), `/tmp/sf-ds4-1flash.lock` is free and no other process has 8 GiB
   or more resident.
2. **Warm-up.** One A and one B run per kind, untimed. Tokens are compared
   here, and with `--bitwise` every prefill and decode logits dump as well, so
   a correctness failure stops the harness early.
3. **Timed rounds.** A B B A quads per kind while the next one fits in
   `--budget` (1800 s, at most 3600) minus the guards' reserve. Pairs are
   (A1, B1) and (B2, A2). Per metric the summary gives the A and B medians,
   the median gain over valid pairs and its bootstrap 95% interval. Every gain
   is printed so that positive is faster: B/A for tokens/s, A/B for seconds.
   A pair is dropped when one of its runs ran below `--min-freq-of-median`
   (0.90) of its kind's median GPU frequency (an external disturbance; the
   median is per kind because a sweep-heavy kind idles the GPU and runs it
   slower by nature); the thermal state never drops a run. `--preheat` (0) keeps the optional
   untimed load before the timed rounds.
4. **Guards.** Each kind named with `--guards` runs once, A then B, after the
   quads: one gain, no interval, marked in the summary.

Kinds (`--kinds` takes names or the groups `cold`, `guards`, `all`; there is
no default, each change names what its phase needs):

| Kind | Frontiers | Tokens | Metrics | Shape it measures | Run time |
|---|---|---|---|---|---|
| `decode` | 2048, 8192 | 256 | `decode 2048`, `decode 8192` (steady tokens/s), first token ms | decode at 2K and 8K of context | 77-84 s |
| `cold-2500` | 2500 | 16 | `ttft 2500` (s) | one sweep plus 452 token-major tokens | 46-50 s |
| `cold-3500` | 3500 | 16 | `ttft 3500` | two sweeps | 41-45 s |
| `cold-5000` | 5000 | 16 | `ttft 5000` | a 4096-row sweep plus 904 token-major | 75-84 s |
| `cold-7500` | 7500 | 16 | `ttft 7500` | a 6144-row sweep plus a 1356 chunk | 51-54 s |
| `cold-10000` | 10000 | 16 | `ttft 10000` | an 8192-row sweep plus a 1808 chunk | 49-51 s |
| `append` | 5000, 5300, 6800 | 16 | `append +300`, `append +1500` (s) | a token-major append and a one-chunk append on a 5000 context | 118-123 s |
| `guard-16896` | 16896 | 16 | `guard ttft 16896` | two 8192-row sweeps plus 512 token-major: the >10K guard | 74-76 s |
| `guard-decode` | 8192 | 2500 | `guard decode 2500` | a long answer at 8K: the >2000-token guard | 172-173 s |

`ttft` is the prefill time of a cold prompt, from an empty context to the
first token's logits. The summary also prints `e2e`: the estimated request
time of the typical mix (prompts of 2500-10000 tokens, answers of 200, 1000
and 2000) from the A and B medians; a kind not run is held at the reference
values in the script (the start commit's figures) on both sides, and the
summary names it.

`--env KEY=VALUE` sets a variable for both builds (inherited `DS4_*` variables
are dropped); `--b-env KEY=VALUE` sets one for B only, on top of `--env`, so a
switch is measured on one tree (`--a . --b . --b-env NAME=1`).
`--bench-arg=ARG` appends ARG to both builds' bench command and
`--b-bench-arg=ARG` to B's only (repeatable; write the `=` form, since ARG
starts with `--`). A summary made with bench arguments or `--b-env` prints no
record row. `-m` selects another GGUF; the default is this checkout's
`deepseek-v4.1-flash.gguf`, resolved to an absolute path for both trees.

The expert read path is diagnosed outside the harness:
`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1` with the bench's `--cache-stats`
prints, with each memory report, the expert timing (`sync` is the wait at the
per-layer selected-id readback, not the loads) and a `streaming pread pool`
line: dispatches, tasks and workers per dispatch, `qd_avg` (task time over
wall time, the concurrency the pool sustains), `pool_gbps` and `task_gbps`.
Its counters are cumulative, so subtract a short run from a long one at the
same frontier to isolate decode (`perf-record.md`, Read path).

Exit status: 0 correct, with a verdict; 1 tokens or bits differ, or a run
failed; 2 refused or aborted (usage, tree, preflight, cache window, the GPU
monitor stopped); 3 inconclusive (a headline metric has fewer than two
pairs). Everything lands in one directory (default
`$TMPDIR/sf-ds4-1flash-ab/<UTC time>`): `summary.txt`, `samples.csv` (one row
per timed run and frontier, with the cache counters, GPU frequency,
temperature, power and a token hash), `gpu.json` (raw `mactop` log), each
run's stderr and CSV, and the warm-up logits dumps.

Noise floor, A/A on the M5 Max (2026-09-27, `--kinds decode,cold-2500,cold-5000
--bitwise --budget 1800`: 26 runs, 10 pairs, every pair kept): the interval of
the median gain read -2.1..+0.5% for `decode 8192` and -2.4..+2.3% for
`ttft 2500` (four pairs each), -0.2..+0.2% for `ttft 5000` (two pairs), but
-6.8..+8.1% for `decode 2048`, whose single runs ranged 16.1-17.9 tokens/s
with identical cache counters and bytes read: at 2048 the cache holds one
sweep's seeding (hit rate 0.87 against 0.90 at 8192) and the miss service
varies run to run. Read `decode 8192` as the tighter decode figure, and pool
invocations for a `decode 2048` claim under about 5%. The first-token latency
after a sweep (1.7-2.8 s) varies by up to ±60% and is reported as detail
only; after a token-major tail it is 60-85 ms. The thermal state went Heavy
within the first two minutes of every run set and stayed there, with the
GPU at 1350-1600 MHz and 16-24 W, fluctuating without a trend: the machine
is SSD-bound, there is no plateau to wait for, and `--preheat` defaults to 0.
Identical runs give identical hit and miss counts, so `--cache-tolerance`
0.01 has no false drops. A second A/A of every kind with two pairs each read
`ttft 3500` at -6.0% and `append +1500` at +7.8%: sweep-only metrics vary
6-8% per pair between identical builds, and an interval over two pairs is
just their range. A claim on a sweep-only metric needs at least six pooled
pairs; `decode 2048` about the same; `decode 8192`, `ttft 2500` and
`ttft 5000` four. In three 600 s invocations the first timed run ran at
0.86-0.88 of its kind's median frequency, 3-5% slower, and was dropped by
the frequency rule: use the default budget or longer, so that one dropped
pair does not leave the verdict inconclusive. An eviction-policy change in B
(hotness decay 16 -> 4 tokens) moved the miss count by 0.7% of the lookups,
under the count tolerance, but the bytes read by 6%, over the 5% rule: the
bytes rule is the finer of the two.

**Pooling.** `ab_pool.py <kind> --metric <name> <out dir>...` pools the pair
gains of several invocations from their `samples.csv` and prints the pooled
n, the median gain and the bootstrap 95% interval, leaving out the pairs the
harness dropped. `openspec/config.yaml` reads that interval for the keep rule.

Two references, two tools:

| What | Reference | Tool |
|---|---|---|
| Quality against the parent project | upstream at the child's merge-base | StarForge `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` |
| Speed against the parent project, informational | upstream at the merge-base, same sweep | StarForge `tools/speed-compare.sh` with `SF_SPEED_FLAGS="--ssd-streaming --ssd-streaming-cache-experts 82GB"` |
| Bitwise identity of a step | this child's `main` or the previous step | `ab_bench.py --bitwise` |
| Speed of a step | this child's `main` or the previous step | `ab_bench.py`, pooled with `ab_pool.py` |

The summary ends with a row for [perf-record.md](perf-record.md), which keeps
where the performance work started and where it has got to.

**Expert-cache replay.** `expert_cache_sim.py --trace FILE --moe-layers N
--slots S [--stderr BENCH_STDERR]` replays a `DS4_MOE_RECORD_SELECTED_IDS`
trace through LRU and Belady caches of S slots and prints both miss counts
next to the measured misses of the same run; `--self-test` checks the two
replays on a known sequence. It answers whether a cache-policy change is
worth opening (see the Situation 0 section of the record).

### Metal decode schedule A/B

Build the balanced, same-engine Metal decode comparison with:

```
make metal-decode-schedule-bench
./speed-bench/metal_decode_schedule_bench \
  -m deepseek-v4.1-flash.gguf \
  --ssd-streaming --ssd-streaming-cache-experts 82GB \
  --include-selection
```

`--ssd-streaming` and `--ssd-streaming-cache-experts N|NGB` mean what they
mean for the other binaries; on a 128 GB Mac the first is required.

The harness prefills two sessions and alternates both variant order and
variant-to-session assignment. It aborts unless every full-vocabulary logit
row is bit-identical and, with `--include-selection`, both variants select the
same non-EOS token. Use `--candidate-env NAME` to measure a rollback control,
or `--help` to compare explicit split schedules.

Single-box decode queues its layers and commits each without waiting (the
token drains at layer 13 and before the logits). Two switches restore the old
schedule: `DS4_METAL_DISABLE_V41_DECODE_QUEUE=1` drains after every layer,
`DS4_METAL_DISABLE_V41_DECODE_FLUSH=1` keeps the queue but commits only at the
drains. To measure the queue against the per-layer drain on the same engine:

```
./speed-bench/metal_decode_schedule_bench \
  -m deepseek-v4.1-flash.gguf \
  --ssd-streaming --ssd-streaming-cache-experts 82GB \
  --candidate-env DS4_METAL_DISABLE_V41_DECODE_QUEUE \
  --include-selection --tokens 256
```

Here the candidate is the rollback: on the M5 Max control 23.06 t/s,
candidate 19.90 t/s (2026-09-28).

To compare the default pre-M5 ratio-4 compressor pack/transpose fusion with the
legacy decode path, including token selection, use:

```
./speed-bench/metal_decode_schedule_bench \
  --candidate-env DS4_METAL_DISABLE_PRE_M5_COMPRESSOR_RATIO4_DECODE_PACK_FUSION \
  --include-selection \
  --tokens 1024
```

### Metal prefill variant A/B

Build the balanced prefill comparison. To compare the default resident pre-M5
MXFP4 pair tail-SIMDgroup cull against the original pair kernel, make the
rollback path the candidate:

```
make metal-prefill-variant-bench
./speed-bench/metal_prefill_variant_bench \
  --candidate-env DS4_METAL_DISABLE_PRE_M5_MXFP4_MOE_MM_ID_PAIR_TAIL_SIMDGROUP_CULL
```

To isolate the default routed-down tail-SIMDgroup cull from the retained pair
default, use its down-specific rollback as the candidate:

```
./speed-bench/metal_prefill_variant_bench \
  --candidate-env DS4_METAL_DISABLE_PRE_M5_MXFP4_MOE_MM_ID_DOWN_TAIL_SIMDGROUP_CULL
```

The harness uses one Metal engine and fresh sessions for every run. It warms
both variants with at least 32 tokens, alternates control/candidate order in
ABBA and BAAB blocks, poisons host logit buffers before copying, and aborts
unless every final full-vocabulary logit row is bit-identical. Defaults are an
8192-token prefix, an automatically sized 8193-token context, and two repeats;
use `--help` to override them.

Numeric runtime tuning controls can use `--candidate-value TEXT` (default `1`), and
`--prefill-chunk N` selects the same chunk size for both variants (default
4096). The control unsets the named variable. Use only controls read at
dispatch time: this harness keeps one engine alive and cannot compare settings
cached during initialization.

### Concurrency: many requests at once

`session_concurrency_bench` measures the engine without HTTP overhead.

```sh
make session-concurrency-bench
./speed-bench/session_concurrency_bench -m deepseek-v4.1-flash.gguf \
  --concurrency 1,2,4,8 --ctx 4096 --gen 128 --budget-gib 28 \
  --csv /tmp/concurrency.csv
```

For an interleaved comparison against a diagnostic rollback:

The control unsets the variable; the candidate sets it in alternating ABBA
blocks. Use only controls read at dispatch time. Keep prompts, context, memory
pressure and thermal conditions comparable, and retain generated text when
measuring speculation. `concurrency_sweep.sh` runs each cell in a fresh process.

`serve_concurrency_bench.py` measures the HTTP server, including queueing,
prompt rendering, prefix reuse and streaming:

```sh
python3 speed-bench/serve_concurrency_bench.py \
  --concurrency 8 --prompt-tokens 4096 --max-tokens 128 --requests 32 \
  --ignore-eos --json /tmp/serve-8.json
```

Start the server separately with an appropriate model, context and
`--batched-session 8`. The report includes first-token and inter-token
latency, request latency and throughput. Prompts use fresh nonces;
`--shared-prefix` tests cache reuse instead.
