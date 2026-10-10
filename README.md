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

> **Expert cache: `--ssd-streaming-cache-experts 82GB`** (74.88 GiB dynamic,
> 8078 slots) for every figure in this README unless a section says
> otherwise. It is the fixed measurement configuration and the value for
> normal use. Without the flag the engine picks less (76.62 GiB in total,
> 7498 slots at `--ctx 32768`). The ceiling with every lever on is the
> separate [max_performance_90](#max-performance-on-one-mac) test.

**Against ds4**, same GGUF, same flags, upstream's own bench:

| Measurement | ds4 t/s | sf t/s | sf vs ds4 |
|---|---:|---:|---:|
| prefill, first 2048 tokens | 124.6 | 187.1 | +50.1% |
| prefill, +2048 to context 4096 | 115.8 | 226.8 | +95.8% |
| prefill, +4096 to context 8192 | 205.1 | 403.7 | +96.8% |
| prefill, +8192 to context 16384 | 364.4 | 567.6 | +55.8% |
| prefill, +16384 to context 32768 | 404.3 | 716.8 | +77.3% |
| generation, context 2048 | 12.1 | 28.8 | +136.6% |
| generation, context 8192 | 12.9 | 28.6 | +122.5% |
| generation, context 32768 | 11.6 | 26.6 | +130.1% |
| steady decode, context 2048 | 15.7 | 29.5 | +87.9% |
| steady decode, context 8192 | 16.8 | 29.3 | +74.7% |
| steady decode, context 32768 | 15.7 | 27.1 | +72.9% |

The first token after a prefill took 2.1-3.0 s on ds4 and 0.11-0.16 s here.
Greedy output is token-identical to ds4 (parity oracle, ten prompts).

**How it was measured.** The builds compared are ds4 at the merge-base
`0aaea5a`, measured on 2026-10-05, and this child at
`268-aligned-uncached-reads`, measured on 2026-10-10, on DeepSeek V4.1 Flash
Q2, with the GGUF on the internal drive only (no second-drive copy).
- Both run `ds4-bench` (here `sf-ds4-1flash-bench`) on *I Promessi Sposi* with
  `--ssd-streaming --ssd-streaming-cache-experts 82GB`, context frontiers from
  2048 to 32768 doubling, and 128 generated tokens per frontier. Each frontier
  prefills the new tokens on top of the previous context.
- Each value is the mean of two runs per build, 180 s apart. ds4 ran on
  2026-10-05 in the order ds4, sf, sf, ds4; this child's two runs are from
  2026-10-10. The CSVs are in `speed-bench/v41-q2-vs-ds4-20261005` (ds4) and
  `speed-bench/v41-q2-sf-20261010` (sf).
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

Measured on 2026-10-09 (`main` at `8e9a954`) with `speed-bench/ab_bench.py`,
expert cache **`82GB`**, copy on APFS, internal SSD only against the same
build with the copy, two invocations pooled. The times are the second
invocation's medians; the gain is the pooled median.

| Shape | Internal SSD only | With the copy | Gain |
|---|---|---|---|
| 2500-token prompt, time to first token | 30.8 s | 27.9 s | +10.4% |
| 3500-token prompt | 13.7 s | 11.4 s | +19.7% |
| 5000-token prompt | 52.5 s | 50.4 s | +4.5% |
| 7500-token prompt | 20.0 s | 17.8 s | +12.8% |
| 10000-token prompt | 28.5 s | 26.2 s | +6.5% |
| append 1500 tokens to a 5300-token conversation | 10.0 s | 7.9 s | +12.0% |
| append 300 tokens | 12.9 s | 12.7 s | +0.4% (within noise) |
| decode after 2048 tokens | 23.0 tokens/s | 23.0 tokens/s | -0.2% (within noise) |
| first token after an 8192-token context | 1.24 s | 0.88 s | 0.36 s sooner |
| decode after 8192 tokens, steady | 23.4 tokens/s | 23.1 tokens/s | -0.6% |
| 256 tokens after an 8192-token context, first included | 12.1 s | 11.9 s | +1.9% |
| typical mix (harness estimate) | | | +3.0% |

The copy speeds up the layer sweeps of a prompt, not the tokens read one at
a time after them. The 5000-token prompt spends most of its time in a
904-token tail at decode speed, so it gains least; 3500, 7500 and 10000 are
almost all sweeps. Decode never reads the copy.

In this table the first token after an 8192-token context is slow in both
columns. The prompt's sweep pushed model pages out of memory: its reads are
meant to bypass the page cache, but on APFS a read that does not start on a
16 KiB page leaves about a quarter of its pages there. Since
`268-aligned-uncached-reads` (2026-10-10) the sweep reads from a page
boundary, and that first token takes about 0.15 s with or without the copy
(harness: 1230 -> 150 ms on the internal SSD only, 1049 -> 132 ms with the
copy). The copy's 0.6% lower steady rate fits what `268` traced, although it
was not measured on that run: a GPU that waited longer for the first token
runs the next 256 tokens at a higher clock
([speed-bench/perf-record.md](speed-bench/perf-record.md), Uncached reads from
a page boundary).

Both together:

```sh
DS4_METAL_PREFILL_REPLICA=/Volumes/<drive>/sf-ds4-1flash/DeepSeek-V4.1-Flash-Q2.gguf \
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

`max_performance_90` is a test run from time to time to see the most one Mac
gets with every lever on at once, against the `82GB` figures above:
- the expert cache at `--ssd-streaming-cache-experts 90GB`, with a 256K
  context allocated;
- Metal's working-set limit raised so that cache fits:
  `sudo sysctl iogpu.wired_limit_mb=117500`;
- the copy on the second drive (`DS4_METAL_PREFILL_REPLICA`);
- `--boost`: full fans through the `fanboost` daemon (it must be running) and
  the GPU keep-alive during decode miss reads.

It is not a step of the A/B harness and changes no default: normal use and
every measurement stay at `82GB` with the system limit. Start it on a cool
machine, with nothing else running.

```sh
sudo sysctl iogpu.wired_limit_mb=117500
DS4_METAL_PREFILL_REPLICA=/Volumes/<drive>/sf-ds4-1flash/DeepSeek-V4.1-Flash-Q2.gguf \
  ./sf-ds4-1flash-bench -m deepseek-v4.1-flash.gguf \
  --prompt-file speed-bench/promessi_sposi.txt \
  --ssd-streaming --ssd-streaming-cache-experts 90GB --boost \
  --ctx-start 2048 --ctx-max 32768 --step-mul 2 --gen-tokens 128 \
  --ctx-alloc 262144 --csv max_performance_90.csv
sudo sysctl iogpu.wired_limit_mb=0    # back to the default; a reboot does it too
```

Why these values:
- **The cap.** The engine caps an explicit cache at 7/8 of Metal's recommended
  working set less the context buffers. With the default limit (107.52 GiB on
  this machine) that is 86 GiB at a 32K context and 83 GiB at 256K, so `90GB`
  would be cut. With the limit at 117500 MiB, 90 GiB fits beside the 10.38 GiB
  of buffers a 256K context needs. If the log still says `capped to`, the
  limit did not take.
- **Memory left to macOS.** The cache, the context buffers and the 9.37 GiB of
  static weights leave about 18 GiB to macOS and other apps, against about
  26 GiB at `82GB`.
- **Why not more.** A replay of the decode expert ids (`speed-bench/perf-record.md`,
  Memory levers) stops gaining decode at about 89 GiB; more cache helps only
  appends, and every GiB comes out of the file cache, which serves 20-28% of
  today's miss reads.

Results: not run yet. The first run fills a table with the same rows as
**Against ds4**, plus the `82GB` column for comparison.

## Supported hardware

* **Metal**, the primary target, on Macs with 96 GB or more. Smaller machines
  can use SSD streaming. SSD streaming is also needed in order to run very
  larger quantizations on 128 GB systems.

This project would not exist without **llama.cpp and GGML**, make sure to read
the acknowledgements section, a big thank you to Georgi Gerganov and all the
other contributors.


# So, what can I do with this software?

* You can run a very capable models in your consumer hardware, a MacBook for example. Even if you have not enough RAM, with SSD streaming, you can run it at a decent speed.
* Using two 128 GB Macs connected with RDMA, you can run this model resident with tensor parallelism.
* You can also use pipeline paralellism to glue together multiple systems to sum their RAM and run larger models.

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

For a first run on a 96 or 128 GB machine, download the Q2 release:

```sh
./download.sh q2
```

The model itself lives once in the shared Hugging Face cache; `gguf/` holds
symlinks to it and `./deepseek-v4.1-flash.gguf` points at the main model.
Repeat the command to verify or resume. Leave memory for the context and
runtime buffers as well as the model. See [the model guide](docs/MODELS.md)
or use [SSD streaming](docs/SSD_STREAMING.md) on a smaller Mac.

## Everyday Use

Once built and with a model downloaded:

```sh
./sf-ds4-1flash
./sf-ds4-1flash -p "Explain Redis streams in one paragraph."
./sf-ds4-1flash-server --ctx 32768
```

The default model is `deepseek-v4.1-flash.gguf`, a link updated by
`./download.sh q2`. Pass `-m FILE` to choose explicitly. Commands normally run
from the repository root; use `--chdir /path/to/sf-ds4-1flash` when launching
elsewhere.

The server listens at `http://127.0.0.1:8002` by default; see [serving](docs/SERVER.md)
for API access and multiple sessions.

The interactive CLI keeps a multi-turn conversation. Use `/help`, `/read FILE`,
`/ctx N`, and `/quit`. Ctrl+C interrupts generation and returns to the prompt.
Run each binary with `--help` for its full options.

For Pi, OpenCode, Codex CLI, or Claude Code, use `sf-ds4-1flash-server` and
follow the [client setup guide](docs/CLIENTS.md).

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
- It asks the owner's `fanboost` daemon, if installed, for full fans while the GPU works. The fans go back to the Apple
  curve about 10 s after the engine goes idle. In a 30-minute session of
  typical requests (expert cache `82GB`) the machine never reached the Heavy thermal state (without
  it, inside the first request), and requests ran about 4-5% faster. Without
  the daemon it only touches `/tmp/fanboost.lease`.
- Under SSD streaming, it keeps the GPU busy while a decode token waits for
  missing experts. That is worth a few tenths of a percent of decode on a
  cool machine.

Directional steering is present in the build and documented under
[dir-steering/](dir-steering/README.md), but DeepSeek V4.1 Flash does not
support it: passing `--dir-steering-file` makes the engine refuse to start,
exactly as it does upstream.

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

## Detailed Guides

- [The model and vision](docs/MODELS.md): downloads, memory, and the encoder.
- [SSD streaming](docs/SSD_STREAMING.md): run larger than RAM and size the cache.
- [Inference across machines](docs/DISTRIBUTED.md): two-Mac TP/RDMA and layer pipelines.
- [Serving](docs/SERVER.md): APIs, images, batching, and disk KV caches.
- [Coding agent clients](docs/CLIENTS.md): Pi, OpenCode, Codex CLI, and Claude Code.
- [Performance](docs/PERFORMANCE.md): reproducible measurements and recorded baselines.
- [Testing and development](docs/TESTING.md): regression tests, debugging, and model-building tools.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before sending a pull request.

## Logo

The DwarfStar logo was designed by hand by Salvatore Sanfilippo, made more
graphical with AI, and manually reworked by Ben Gnomino, whose human touch made
it rock.
