# sf-ds4-1flash

`sf-ds4-1flash` is a specialized fork of [ds4 / DwarfStar](https://github.com/antirez/ds4)
by Salvatore Sanfilippo and contributors, reduced to **DeepSeek V4.1 Flash** on
**Apple Metal**. The upstream commit this fork sits on is not written here:
ask git, which cannot go stale --
`git describe --tags --match 'sync-*' --abbrev=0` for the last sync, or
`git merge-base HEAD upstream/main` for the base itself.
Everything that works here works because of ds4, llama.cpp and GGML; see
`LICENSE` and the acknowledgements below.

The code is self-contained and deliberately narrow, not a general GGUF runner:
it loads the GGUF files the ds4 project produces, and refuses anything whose
`general.architecture` is not `deepseek41`.

We test things in integration: model loading, prompt rendering,
tool calls, KV state, and the HTTP server are built and tested together.
The repository also includes tools and data for quality and speed measurement.

> **Use at your own risk.** This project, including the bundled `fanboost`
> fan daemon, is provided as is, without warranty of any kind (see
> `LICENSE`). Whoever builds, runs or changes it does so at their own risk
> and is solely responsible for the consequences. The author accepts no
> liability for any damage to hardware, data or anything else.

## Why this fork exists

ds4 is built around a few models rather than as a general GGUF runner, and it
is meant to be read and changed with a coding agent: a working template to
adapt to your model and hardware, not a product that covers every setup (see
"How to use this project" below). This fork pushes both ideas to the end: one
model, one backend, and nothing else in the tree. Code for other models, other
GPU backends and the bundled agent is deleted, not hidden behind flags. The
result is a source tree small enough that a person, or an LLM, can load it
whole and see how DeepSeek V4.1 Flash actually runs, which makes it cheap to
try an idea, measure it and keep or drop it.

Metal is the only GPU backend because the only hardware this fork is developed
and tested on is an Apple M5 Max.

The smaller tree is also what makes the rest of this work possible: open pull
requests on ds4 are analysed against this one model and ported where they hold
up (`docs/upstream-prs.md` records the verdicts), and further improvements are
investigated for Apple Silicon. None of it changed what the model writes:
every speed-up so far keeps the output bit for bit identical (see "Speed
without changing the output" below).

## Speed

> **Hardware.** Every performance number in this repository was measured on
> one machine: an Apple **M5 Max with 128 GB** of unified memory, with the
> Q2 GGUF streamed from its internal SSD. Other Macs will give different
> absolute numbers.

On a 128 GB Mac this model always runs with `--ssd-streaming` (see
`AGENTS.md`), so every figure here is a streaming figure.

> **Expert cache: `--ssd-streaming-cache-experts 80GB`** (72.40 GiB dynamic,
> 7810 slots) for every figure in this README unless a section says
> otherwise. It is the fixed measurement configuration and the value for
> normal use. Without the flag the engine picks less (76.62 GiB in total,
> 7498 slots at `--ctx 32768`). The A/B harness keeps `82GB`
> ([speed-bench/README.md](speed-bench/README.md)). The ceiling with every
> lever on is the separate [max_performance_80](#max-performance-on-one-mac)
> test.

**Against ds4**, same GGUF, same flags, upstream's own bench:

| Measurement | ds4 t/s | sf t/s | sf vs ds4 | sf `--boost` t/s | sf `--boost` vs ds4 |
|---|---:|---:|---:|---:|---:|
| *commit* | `b3f5018` | `6898b39` | *+ is better* | `6898b39` | *+ is better* |
| prefill, first 2048 tokens | 120.9 | 182.9 | +51.3% | 179.4 | +48.4% |
| prefill, +2048 to context 4096 | 110.3 | 238.2 | +116.0% | 235.0 | +113.1% |
| prefill, +4096 to context 8192 | 202.8 | 423.8 | +109.0% | 418.9 | +106.6% |
| prefill, +8192 to context 16384 | 332.2 | 561.0 | +68.9% | 605.5 | +82.3% |
| prefill, +16384 to context 32768 | 483.1 | 701.7 | +45.2% | 722.9 | +49.6% |
| generation, context 2048 | 10.3 | 29.3 | +184.5% | 29.5 | +186.4% |
| generation, context 8192 | 16.6 | 30.4 | +83.1% | 30.4 | +83.1% |
| generation, context 32768 | 14.1 | 28.8 | +104.3% | 29.1 | +106.4% |
| steady decode, context 2048 | 14.7 | 30.7 | +108.8% | 30.9 | +110.2% |
| steady decode, context 8192 | 24.1 | 31.8 | +32.0% | 31.6 | +31.1% |
| steady decode, context 32768 | 22.3 | 30.2 | +35.4% | 30.3 | +35.9% |

First token after each prefill, same runs:

| Context | ds4 ms | sf ms | sf vs ds4 | sf `--boost` ms | sf `--boost` vs ds4 |
|---|---:|---:|---:|---:|---:|
| *commit* | `b3f5018` | `6898b39` | *- is better* | `6898b39` | *- is better* |
| 2048 | 3817 | 227 | -94.0% | 225 | -94.1% |
| 4096 | 2727 | 234 | -91.4% | 214 | -92.2% |
| 8192 | 2435 | 221 | -90.9% | 216 | -91.1% |
| 16384 | 3365 | 221 | -93.4% | 197 | -94.1% |
| 32768 | 3390 | 231 | -93.2% | 216 | -93.6% |

sf locks its 9.37 GiB of static weights at this cache (`760`; AGENTS.md, SSD
streaming), while ds4 leaves them pageable. Pageable static weights cost time
once the file cache is full and free memory sits at the kernel's floor: the
GPU then waits for the kernel to wire them. That is the state every run here
starts in. The first 2048 tokens went from 144.4 tokens/s (`82GB`, before
`760`, earlier the same day: [speed-bench/readme-20261107](speed-bench/readme-20261107))
to 182.9. ds4's decode at context 2048 is the noisiest row: its three runs
spread over 12.3-16.7 tokens/s.

**Every run starts from the same cool chip, and the long ones end hot.**
Before each run the fans cool the chip to 47.5 °C and macOS back to thermal
pressure Nominal; then plain runs follow Apple's fan curve. An sf sweep takes
92-96 s: the chip reaches 100-101 °C and macOS stays at Nominal. ds4's takes
162-166 s, peaks at 99-100 °C and also stays at Nominal. With
`--boost` the fans run at their maximum and the chip peaks at 99-100 °C. In a
sweep this short that buys +8% on the prefill to 16384 and +3% (within noise)
on the one to 32768, which come last when the chip is hottest, under 1% on
steady decode, and nothing on the first three frontiers; in a 30-minute
session of requests it is worth about 4-5% (see `--boost` below).

The first token is the noisiest figure. sf reads experts uncached, so its
first token depends on which expert pages earlier processes left in the page
cache: the same build read 0.10-0.14 s in one series of runs and 0.15-0.21 s
in the next, after a ds4 run had passed through
([speed-bench/perf-record.md](speed-bench/perf-record.md), README sweep
protocol). Against ds4's 2-3 s the comparison holds; between the two sf
columns the differences are within that noise.

Greedy output is token-identical to ds4 (parity oracle, ten prompts).

**How it was measured** on 2026-11-07 by `speed-bench/readme_bench.py sweep`.
The builds compared are ds4 at the merge-base `b3f5018` and this child at
`main` `6898b39`, on DeepSeek V4.1 Flash Q2 (`1017`), with the GGUF on the internal drive
only (the second-drive columns of the same session are in
[A second drive](#a-second-drive)).
- Both run `ds4-bench` (here `sf-ds4-1flash-bench`) on *I Promessi Sposi* with
  `--ssd-streaming --ssd-streaming-cache-experts 80GB`, context frontiers from
  2048 to 32768 doubling, and 128 generated tokens per frontier. Each frontier
  prefills the new tokens on top of the previous context.
- Each value is the median of three runs. ds4's three runs come first, then
  the sf columns, rotated; each block starts with a discarded warm-up run of
  its own build. A run that follows a ds4 run loses 4-6% on the first 2048
  tokens, sf or ds4 alike, because ds4's prefill leaves 13 GiB more of the
  GGUF in the page cache; ds4's figures are therefore runs that follow ds4
  (after an sf run it reads 129 tokens/s on the first 2048 tokens, not 121).
- Before every run `fanboost max` until the chip is at or below 47.5 °C (its
  lowest reading in 60 s of full fans after the warm-up, plus 2 °C) and macOS
  reports Nominal, then back to Apple's curve, with fanboost's own thermal
  protection paused. Chip and fans are sampled every 2 s with
  `fanboost status`, thermal pressure and GPU clock every second with mactop.
  The CSVs, medians and per-run conditions are in
  `speed-bench/readme-20261107-80gb/sweep`; the protocol is in
  `speed-bench/README.md`, "README tables".
- "Generation" counts all 128 tokens, including the first one after the
  prefill; "steady decode" leaves that first token out.

Every step between ds4 and this tree is judged by `speed-bench/ab_bench.py`,
which alternates the two builds in A B B A runs, drops pairs whose GPU clock
sagged or whose expert cache diverged, and reports medians with bootstrap 95%
intervals for decode, time to first token on cold prompts of 2.5K-10K tokens,
and appends to a live session. A step is kept only when its target gains and
no other metric clearly loses. Each change appends a row to
`speed-bench/perf-record.md` against a fixed start commit.

See [performance and benchmarking](docs/PERFORMANCE.md) for the full numbers,
comparison conditions, and benchmark commands.

## Speed without changing the output

**Every performance change so far has left the model's output bit for bit
identical.** No precision is traded for speed: no lower-precision KV cache, no
approximate kernel, no route that changes a single logit.

| Path | Guarantee |
|---|---|
| Prefill and decode | logits **bit-identical** to the build before each step (`speed-bench/ab_bench.py --bitwise`); every step in `speed-bench/perf-record.md` passed that bitwise gate |
| Against upstream ds4 | greedy output **token-identical** to ds4 at the merge-base (StarForge parity oracle, ten prompts) |

**How it is checked.** Every change goes through four checks:
- the StarForge parity oracle (`tools/parity-check.sh`) runs ten prompts
  greedily on this child and on upstream ds4 at the child's merge-base, with
  the same GGUF, and requires token-identical output;
- the A/B harness requires identical tokens against the previous build, and
  bit-identical logits (`--bitwise`) when a change claims it;
- every runtime switch that turns a speed-up off is checked with
  `make test-deepseek41-decode-switch SWITCH=<env>`: 65 decode tokens with and
  without it, logits, Engram history and KV state compared bit for bit;
- kernel tests compare optimized kernels with the CPU reference or with the
  kernel they replace.

## A second drive

An external SSD has two uses here. The one measured is a Samsung 9100 PRO
1 TB (APFS since 2026-10-08, ExFAT before) in an ACASIS TB501 Pro enclosure
on Thunderbolt 5, 80 Gbit/s.
Inside, the enclosure runs the drive at PCIe 4.0 x4, which caps reads at
about 6.4 GB/s, half the internal SSD ([docs/ssd.md](docs/ssd.md)). Other
enclosures and links will give different figures.

- **Faster prompts.** Put a byte-identical copy of the GGUF on it, for example
  with `cp`, and pass it as `DS4_METAL_PREFILL_REPLICA`. Long prompts then read
  part of each layer's weights from each drive at once (table below). The
  first start compares the copy with the model (about 7 s on that drive) and
  refuses to start on any difference. A pass is stamped on the copy, so later
  starts skip the comparison until either file changes.
  `DS4_METAL_PREFILL_REPLICA_FULL_CHECK=1` forces it, for example after
  copying the GGUF with a tool that keeps the old modification time.
- **Less wear on the internal SSD.** Reading does not wear an SSD; writing
  does. During inference the server writes only its disk KV cache, 1-2
  checkpoints of 23-49 MiB per request. A Mac's internal SSD is soldered to the
  board, so put that cache on the replaceable drive with `--kv-disk-dir`. On
  APFS it costs nothing: a store takes 6.5 ms less than on the internal SSD,
  a load 4 ms more.

Measured on 2026-11-07 (`main` at `6898b39`) by
`speed-bench/readme_bench.py shapes`: the A/B harness's prompt, append and
decode shapes, expert cache **`80GB`**, copy on APFS, three runs per column
in rotated order, each started once the fans had cooled the chip to 40.5 °C
or below and macOS reported Nominal, plain columns on Apple's fan curve. Each run lasts 13-45 s
and stays at Nominal, so this is one request on a rested machine. Times are
medians; the gain is against the internal SSD only, + is better. *Within
noise*: the three runs of that column overlap those of the internal SSD.

| Shape | Internal SSD only | With the copy | Gain | Copy and `--boost` | Gain |
|---|---|---|---|---|---|
| 2500-token prompt, time to first token | 11.5 s | 8.6 s | +34.8% | 8.5 s | +34.9% |
| 3500-token prompt | 11.9 s | 8.9 s | +33.2% | 8.9 s | +33.2% |
| 5000-token prompt | 12.2 s | 10.1 s | +20.8% | 10.1 s | +20.7% |
| 7500-token prompt | 14.4 s | 13.1 s | +10.5% | 13.0 s | +11.2% |
| 10000-token prompt | 21.2 s | 18.5 s | +14.9% | 18.4 s | +15.2% |
| append 1500 tokens to a 5300-token conversation | 7.8 s | 5.7 s | +37.1% | 5.6 s | +37.7% |
| append 300 tokens | 9.7 s | 8.9 s | +9.7% (within noise) | 8.9 s | +9.7% (within noise) |
| decode after 2048 tokens | 30.9 tokens/s | 32.3 tokens/s | +4.6% (within noise) | 32.4 tokens/s | +4.7% (within noise) |
| first token after an 8192-token context | 0.21 s | 0.20 s | same (within noise) | 0.16 s | same (within noise) |
| decode after 8192 tokens, steady | 31.7 tokens/s | 32.3 tokens/s | +1.9% (within noise) | 32.1 tokens/s | +1.3% (within noise) |
| 256 tokens after an 8192-token context, first included | 8.3 s | 8.1 s | +1.7% (within noise) | 8.1 s | +1.8% (within noise) |
| typical mix (harness estimate) | 48.4 s | 44.8 s | +8.0% | 44.9 s | +7.9% |

The copy speeds up the layer sweeps of a prompt, not the tokens read one at
a time after them. Decode never reads the copy, and its rows here are within
noise. Since the `b3f5018` sync every prompt in this table is almost all
sweeps (a 5000-token prompt no longer ends in a 904-token tail at decode
speed). The gain falls from a third at 2500-3500 tokens to 10-21% from 5000
tokens on, and in one request this short `--boost` adds nothing: the two copy
columns are within 1% on every prompt. Earlier the same day, at `82GB` with
the static weights pageable ([speed-bench/readme-20261107](speed-bench/readme-20261107)),
the copy alone gained +2.7% and -3.2% at 5000 and 7500 tokens against +27%
and +14% with `--boost`; at `80GB` with the static weights locked this
session shows no such gap.

Under sustained load the copy gains less. The 2026-10-10 harness run, an hour
at thermal pressure Heavy with the GPU at 1030-1070 MHz and decode at about
24 tokens/s, read +7.4% on the 2500-token prompt, +13.9% on the 1500-token
append and +1.3% on the typical mix, against +31.0%, +37.7% and +5.5% here:
when the GPU clock is the limit, faster reads matter less
([speed-bench/perf-record.md](speed-bench/perf-record.md), External drive
after 268).

Upstream's bench sweep from [Speed](#speed), same session and protocol, with
the copy (gain against the internal SSD only, + is better, *within noise* as
above):

| Measurement | sf t/s | sf + copy t/s | Gain | sf + copy `--boost` t/s | Gain |
|---|---:|---:|---:|---:|---:|
| prefill, first 2048 tokens | 182.9 | 243.3 | +33.0% | 240.4 | +31.4% |
| prefill, +2048 to context 4096 | 238.2 | 298.2 | +25.2% | 310.0 | +30.1% |
| prefill, +4096 to context 8192 | 423.8 | 461.2 | +8.8% | 477.5 | +12.7% |
| prefill, +8192 to context 16384 | 561.0 | 575.6 | +2.6% (within noise) | 647.4 | +15.4% |
| prefill, +16384 to context 32768 | 701.7 | 726.1 | +3.5% | 763.4 | +8.8% |
| generation, context 2048 | 29.3 | 29.4 | +0.3% (within noise) | 29.1 | -0.7% (within noise) |
| generation, context 8192 | 30.4 | 30.2 | -0.7% (within noise) | 30.0 | -1.3% (within noise) |
| generation, context 32768 | 28.8 | 28.8 | 0.0% (within noise) | 28.6 | -0.7% (within noise) |
| steady decode, context 2048 | 30.7 | 30.7 | 0.0% (within noise) | 30.3 | -1.3% (within noise) |
| steady decode, context 8192 | 31.8 | 31.6 | -0.6% (within noise) | 31.6 | -0.6% (within noise) |
| steady decode, context 32768 | 30.2 | 29.9 | -1.0% (within noise) | 30.1 | -0.3% (within noise) |

The copy adds a third on the first frontier, a quarter on the second and
3-9% on the long ones; with `--boost` the long ones gain 9-15%, which makes
copy and `--boost` together the fastest configuration measured at the `80GB`
cache. The first token after each prefill is 0.19-0.25 s in all three
columns. The CSVs are in `speed-bench/readme-20261107-80gb`.

Both together:

```sh
DS4_METAL_PREFILL_REPLICA=/Volumes/<drive>/sf-ds4-1flash/DeepSeek-V4.1-Flash-1017-IQ2_XXS-Q2_K-imatrix.gguf \
  ./sf-ds4-1flash-server --ssd-streaming --ctx 32768 \
  --kv-disk-dir /Volumes/<drive>/sf-ds4-1flash/kv --kv-disk-space-mb 4096
```

To move an existing cache once, stop the server and run
`mv ~/.sf/ds4-1flash/kv/*.kv /Volumes/<drive>/sf-ds4-1flash/kv/`; each file
carries its own eviction state. If the drive is not mounted, the engine
refuses to start when the copy is configured. Without the copy, the server
logs that it cannot create the cache directory and runs without a disk cache.
The drive slows to about 1 GB/s only after 45-50 GiB
written in one continuous burst, while its fast write cache is full
([docs/ssd.md](docs/ssd.md)). The KV cache writes 23-49 MiB at a time, so it
never gets there; copying the 341 GiB GGUF does. The measurements are in
[speed-bench/perf-record.md](speed-bench/perf-record.md) (Dual-drive prefill
after 132, KV cache placement after 150, External drive on APFS).

## Max performance on one Mac

`max_performance_80` is a test run from time to time to see the most one Mac
gets with every lever on at once, against the plain `80GB` figures of
[Speed](#speed):
- the expert cache at `--ssd-streaming-cache-experts 80GB`, with a 256K
  context allocated;
- the copy on the second drive (`DS4_METAL_PREFILL_REPLICA`);
- `--boost`: full fans through the `fanboost` daemon (it must be installed,
  see [fanboost/](fanboost/README.md)) and the GPU keep-alive during decode
  miss reads.

It is not a step of the A/B harness and changes no default. Start it on a cool
machine, with `fanboost` running, macOS at thermal pressure Nominal and
nothing else running.

```sh
DS4_METAL_PREFILL_REPLICA=/Volumes/<drive>/sf-ds4-1flash/DeepSeek-V4.1-Flash-1017-IQ2_XXS-Q2_K-imatrix.gguf \
  ./sf-ds4-1flash-bench -m deepseek-v4.1-flash.gguf \
  --prompt-file speed-bench/promessi_sposi.txt \
  --ssd-streaming --ssd-streaming-cache-experts 80GB --boost \
  --ctx-start 2048 --ctx-max 32768 --step-mul 2 --gen-tokens 128 \
  --ctx-alloc 262144 --csv max_performance_80.csv
```

The log must print `streaming expert cache locked ahead: 7810 of 7810 slots`
and `static weights locked 9.37 GiB`, and neither `capped to` nor `using
locked cache cap`: either line means the engine ran with less cache than
asked.

Why these values:
- **The cache is 80GB**, as in every table of this README. 86, 88 and 90 GB
  were measured against `82GB` (`speed-bench/perf-record.md`, Expert cache
  above the cap):
  - decode +0.3% to +1.3%, and appends of 300 tokens +1.3% to +2.2%;
  - every GiB of cache is a GiB less of file cache, so the first token after
    an 8192-token context slowed from 134 to 157 ms at 86, from 137 to 213 ms
    at 88 and from 121 to 301 ms at 90;
  - at 86 the engine's own pages started to be compressed, and macOS fell to
    7.5 GiB available at the prefill peak.
- **No `sysctl`.** At `80GB` a 256K context fits the default Metal working
  set: it needs 106300 MiB, and the default is 110100. A larger cache needs
  `sudo sysctl iogpu.wired_limit_mb`; [docs/MacM5.md](docs/MacM5.md) gives the
  value per cache and context.
- **256K allocated**, as a long session needs. Its buffers take 10.38 GiB,
  against 7.89 GiB at 32K.

Results, measured on 2026-11-07 in the same `readme_bench.py sweep` session as
**Against ds4** (three runs, medians), with the same rows:

| Measurement | sf `80GB` t/s | `max_performance_80` t/s |
|---|---:|---:|
| *commit* | `6898b39` | `6898b39` |
| prefill, first 2048 tokens | 182.9 | 236.9 |
| prefill, +2048 to context 4096 | 238.2 | 297.1 |
| prefill, +4096 to context 8192 | 423.8 | 448.1 |
| prefill, +8192 to context 16384 | 561.0 | 638.4 |
| prefill, +16384 to context 32768 | 701.7 | 752.9 |
| generation, context 2048 | 29.3 | 29.0 |
| generation, context 8192 | 30.4 | 29.8 |
| generation, context 32768 | 28.8 | 28.4 |
| steady decode, context 2048 | 30.7 | 30.5 |
| steady decode, context 8192 | 31.8 | 31.5 |
| steady decode, context 32768 | 30.2 | 29.7 |

The ceiling is a prefill question:
- The copy and `--boost` add 30% on the first 2048 tokens, 25% on the next
  2048 and 6-14% on the long sweeps.
- Decode is within noise between the two columns (the runs overlap): the
  256K context costs nothing measurable there.
- The copy with `--boost` at a 32K context (the sweep in
  [A second drive](#a-second-drive)) prefilled 1-7% faster at the median,
  with every frontier's runs overlapping these, so allocating 256K costs
  nothing this session can resolve.

## Supported hardware

* **Metal** on Apple Silicon, the only backend. The Q2 GGUF needs
  `--ssd-streaming` on a 128 GB Mac, the only machine this fork is measured
  on. A Mac with room for the ~152 GiB of main weights plus the context can
  run it resident (not measured here), and so can two 128 GB Macs with TP/RDMA.
  The Engram tables stay on disk in every mode.

This project would not exist without **llama.cpp and GGML**, make sure to read
the acknowledgements section, a big thank you to Georgi Gerganov and all the
other contributors.


# So, what can I do with this software?

* You can run a very capable models in your consumer hardware, a MacBook for example. Even if you have not enough RAM, with SSD streaming, you can run it at a decent speed.
* Using two 128 GB Macs connected with RDMA, you can run this model resident with tensor parallelism.
* Pipeline (layer-slice) parallelism across several machines is in the tree but does not work for DeepSeek V4.1 yet ([docs/DISTRIBUTED.md](docs/DISTRIBUTED.md)).

## Motivations

* Capable open-weight models now fit on high-end personal machines.
* DeepSeek V4.1 Flash tolerates aggressive routed-expert quantization.
* Compressed KV caches and fast local SSDs make long contexts practical.
* The idea of an inference system specialized for a few models.

# AI full disclosure

* This software is developed with **strong assistance from AI coding agents** and with humans leading the ideas, testing, and debugging. We say this openly because it shaped how the project was built. If you are not happy with AI-developed code, this software is not for you. The acknowledgement below is equally important: this would not exist without `llama.cpp` and GGML, largely written by hand.

## Acknowledgements to llama.cpp and GGML

`ds4.c` does not link against GGML, but it **exists thanks to the path opened by the
llama.cpp project and the kernels, quantization formats, GGUF ecosystem, and hard-won
engineering knowledge developed there**.
We are thankful and indebted to [`llama.cpp`](https://github.com/ggml-org/llama.cpp)
and its contributors. Their implementation, kernels, tests, and design choices were
an essential reference while building this DeepSeek V4 specific inference path.
Some source-level pieces are retained or adapted here under the MIT license: GGUF
quant layouts and tables, CPU quant/dot logic, and certain kernels. For this
reason, and because we are genuinely grateful, we keep the GGML authors copyright
notice in our `LICENSE` file.

## Status

The software is currently very fast changing. Consider it beta quality.
Before each release, a big QA run is executed, however instabilities
and regressions are definitely possible.

# How to use this project?

I (Salvatore) believe that the way projects should be shipped and used changed because of AI. The main differences today are:

1. With AI, users can modify the software in significant ways with low efforts, costs, and even lacking deep domain knowledge about the task they want to accomplish. For instance, a DwarfStar user with a specific hardware setup can ask a coding agent to improve the inference speed of this software for the specific hardware setup, asking the model to reach the maximum prefill and generation speed without impacting correctness, and also asking to do a deep QA pass.
2. Similiarly, because of "1", software may be shipped in a different way than before. It must be more a working template for the biggest use cases, without trying to cover every possible setup. If DwarfStar showcases a few good implementations of tensor parallel execution, the code will work as a rail for implementing the same feature in specific conditions, for a new model, and so forth.

So, while this project attempts to be usable for the featured models and the most common hardware setups, I ask you, if you have access to coding agents, to consider using coding agents as an interface to discover the project, make modifications, create personalized setups. This way you can likely do more than what we ship, and certain things that are not documented or implemented, and that you require, are potentially very easy to achieve.

## Start Here

```sh
git clone https://github.com/Chida82/sf-ds4-1flash.git
cd sf-ds4-1flash
```

Choose your build. The platform guides cover prerequisites, memory sizing,
and hardware-specific setups:

| Platform guide | Build |
| --- | --- |
| [Metal on Apple Silicon](docs/METAL.md) | `make` |

Download the 1017 release (IQ2_XXS/Q2_K imatrix), the only one offered here:

```sh
./download.sh main
```

The model itself lives once in the shared Hugging Face cache; `gguf/` holds
symlinks to it and `./deepseek-v4.1-flash.gguf` points at the main model.
Repeat the command to verify or resume. On a 128 GB Mac it runs only with
`--ssd-streaming`; see [the model guide](docs/MODELS.md) and
[SSD streaming](docs/SSD_STREAMING.md).

## Everyday Use

Once built and with a model downloaded:

```sh
./sf-ds4-1flash --ssd-streaming
./sf-ds4-1flash --ssd-streaming -p "Explain Redis streams in one paragraph."
./sf-ds4-1flash-server --ssd-streaming --ctx 32768
```

These use the automatic expert cache; every figure in [Speed](#speed) adds
`--ssd-streaming-cache-experts 80GB`.

The default model is `deepseek-v4.1-flash.gguf`, a link updated by
`./download.sh main`. Pass `-m FILE` to choose explicitly. Commands normally run
from the repository root; use `--chdir /path/to/sf-ds4-1flash` when launching
elsewhere.

The server listens at `http://127.0.0.1:8002` by default; see [serving](docs/SERVER.md)
for API access and multiple sessions.

The interactive CLI keeps a multi-turn conversation. Use `/help`, `/read FILE`,
`/ctx N`, and `/quit`. Ctrl+C interrupts generation and returns to the prompt.
Run each binary with `--help` for its full options.

For Pi, OpenCode, Codex CLI, or Claude Code, use `sf-ds4-1flash-server` and
follow the [client setup guide](docs/CLIENTS.md).

### Running as a service

`sfctl` runs the server as an on-demand launchd service on port 8910
(`sfctl start ds4-1flash`, `sfctl stop ds4-1flash`, `sfctl status`). It runs
from its own worktree at `main`, never from your development branch, and never
starts on its own. Install, commands and keeping it in sync with `main`:
[sfctl/README.md](sfctl/README.md).

### Model, images, and memory

[The model guide](docs/MODELS.md) lists the downloads and memory requirements.

DeepSeek V4.1 Flash text and vision run on Metal. Q2 runs with SSD streaming on
one 128 GB Mac, or resident across two Macs using RDMA. Engram tables remain on
disk in every mode, so use a fast local SSD.

With the encoder downloaded (`./download.sh vision`) and passed as
`--vision FILE`, use `/read image.png` in the CLI.

This model has no speculative decoding: `--mtp`, `--dspark` and the external
support GGUF do not exist here.

### Output and power

Thinking is enabled by default. Use `--nothink` or `/nothink` for direct
answers, and `--think` or `/think` to enable it again.
For V4.1, `sf-ds4-1flash` also accepts `--think-level 25` or `/think 25`:
1 to 100 sets the reasoning effort, and 0 disables thinking. `--think`
selects 75, `--think-max` selects 100.
Changing the level in a conversation rebuilds its cached prefix.
The normal sampling defaults are temperature 1, top-p 1, and min-p 0.05;
`--temp 0` selects greedy output.

`--power N` trades throughput for lower sustained GPU load, but this model
requires `--power 100`.

`--boost` (CLI, server and bench) is for interactive use. The output is the
same with and without it. It does two things:
- It asks the `fanboost` daemon for full fans while the GPU works, so it
  needs fanboost installed and running: without it the engine refuses to
  start and says what is missing. The fans go back to the Apple curve a few seconds after the engine
  goes idle, when fanboost's request lapses. In a 30-minute session of
  typical requests (expert cache `82GB`) the machine never reached the Heavy
  thermal state (without it, inside the first request), and requests ran
  about 4-5% faster. It does so by running `fanboost max` once a second.
- Under SSD streaming, it keeps the GPU busy while a decode token waits for
  missing experts. That is worth a few tenths of a percent of decode on a
  cool machine.

The server also has a per-request variant, `--boost-on-max-effort`. It checks
fanboost at startup like `--boost`, then keeps boost off and turns it on only
while at least one request with reasoning effort `max` (or the numeric
`"100"`) is generating, on any API. `xhigh` and lower levels, and a `max`
request with thinking disabled, run without it. Under `--batched-session` the
other requests in the batch share the boost while a max request runs. The log
shows one line when boost turns on and one when it turns off. It cannot be
combined with `--boost`.

`fanboost` ships in [fanboost/](fanboost/README.md); install it with
`./fanboost/install.sh` and remove it with `./fanboost/install.sh uninstall`.
The script builds it, runs its self-test, lists the risks and installs only
after you type `yes`. **Know what it does before installing:**
- it is a root daemon that writes the Mac's fan controller (the SMC) through
  an interface Apple does not document, so a macOS update can break it;
- it only ever sets the fans to their maximum or hands them back to Apple's
  curve, so it cannot cool less than macOS would, and a crash while boosting
  leaves the fans at full speed (noise, not heat). That limits the danger of
  changing the fans; it does not remove it;
- full fans are loud and wear the fans faster;
- any local process can ask it for full fans without `sudo`.

Using it, like the rest of this project, is your own responsibility.

Directional steering is present in the build and documented under
[dir-steering/](dir-steering/README.md). On DeepSeek V4.1 Flash it runs only
through a steering profile: `--steering-profile NAME` loads a complete steered
configuration from one file (both directions, their scales and think/answer
gates), applied at the attention-input fold (change `401`). The CLI keeps
upstream's `--dir-steering-file`, and on V4.1 it makes the engine refuse to
start, exactly as upstream. The shipped profile, how its directions were
derived, and the measurements behind them are in
[com-steering/](com-steering/investigation.md).

`--prefix-file FILE` preloads complete `USER:` / `ASSISTANT:` pairs before
the live conversation. A turn marker must start a line, roles must alternate,
and the last turn must be `ASSISTANT:`.

## Capability Evaluation

`sf-ds4-1flash-eval` runs embedded capability regression tests against a real GGUF.
These are DwarfStar integration checks, not official leaderboard scores.

```sh
./sf-ds4-1flash-eval -m deepseek-v4.1-flash.gguf --trace /tmp/ds4-eval.txt
./sf-ds4-1flash-eval -m deepseek-v4.1-flash.gguf --suite hard-smoke
./sf-ds4-1flash-eval -m deepseek-v4.1-flash.gguf --suite hard --retry-incomplete
```

The default suite is `core`; `--suite all` runs core and hard cases.
`--list-cases` lists tests without loading a model. `--plain` selects
non-interactive output, and `--regrade-trace FILE` scores an existing trace
without generating again. Sources and licenses are in [EVAL_DATA.md](EVAL_DATA.md).
For inference correctness and release checks, read [testing](docs/TESTING.md).

The steering directions were validated with an A/B harness that measured an
intervention as a base run against a steered run, judged by the unsteered model
with two mandatory controls (refusal removal, benign fidelity, over-refusal,
capability, breadth). That investigation is closed and its harness is not
shipped; the method, the KPIs and the accepting runs are recorded in
[com-steering/](com-steering/kpi.md).

## Detailed Guides

- [The model and vision](docs/MODELS.md): downloads, memory, and the encoder.
- [SSD streaming](docs/SSD_STREAMING.md): run larger than RAM and size the cache.
- [Inference across machines](docs/DISTRIBUTED.md): two-Mac TP/RDMA and layer pipelines.
- [Serving](docs/SERVER.md): APIs, images, batching, and disk KV caches.
- [Coding agent clients](docs/CLIENTS.md): Pi, OpenCode, Codex CLI, and Claude Code.
- [Performance](docs/PERFORMANCE.md): reproducible measurements and recorded baselines.
- [Testing and development](docs/TESTING.md): regression tests, debugging, and model-building tools.
- [Steering research](com-steering/investigation.md): the techniques tried, results, KPIs and profiles.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before sending a pull request.

## Logo

The DwarfStar logo was designed by hand by Salvatore Sanfilippo, made more
graphical with AI, and manually reworked by Ben Gnomino, whose human touch made
it rock.
