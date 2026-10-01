# Design

## Context

See proposal.md (Why). Facts from the code and the diffs:

- **Bases.** #1073, #952 and #758 are all based on `0aaea5a`, the child's
  merge-base, so their hunks apply to upstream text the child still carries.
  The heads are fetched as `refs/sfpr/{1073,952,758,864}`. #758 was
  force-pushed since the intake: `e154aa8` -> `a3393d7`.
- **The schedule.** `ds41_prefill_count` (`ds4.c` ~24625):
  - `minimum` is 256 at pos 0 and 1024 at pos > 0 with our cache (the
    "half the experts cached" rule);
  - `remaining ≥ 4096` returns `count - count % 2048`, otherwise
    `min(remaining, 2048)`.

  `tests/test_deepseek41_prefill.c` pins the expected counts and asserts
  that the Metal chunks follow the function (lines 39-75 and 120).
- **The short sweep upstream.** The four #1073 commits are a sequence, not
  independent fixes:
  - `4fbbc4a` opens the wide sweep at 3072;
  - `ccbf2c0` sets the decoder suffix at `1 + (40 - 20) × 127 = 2541` rows;
  - `64240fb` reverts both;
  - `798c64f` redoes them with a tail test.

  Their net, against `0aaea5a`, is `798c64f`'s state:
  - in `ds41_prefill_count`, a wide call from 3072 that keeps the final
    partial tile below 8192 when `!tail || tail >= minimum`;
  - in `ds41_graph_prefill_sweep`, `decoder_suffix` from `suffix_rows`
    instead of 8192. Below 8192, each decoder layer's `first` is rounded
    down to a 2048 tile and warmed with 128 rows, skipped when `first` is 0.

  The `minimum` it tests is the one for the current call, so at pos 0 it is
  256.
- **The decoder suffix.** Decoder layers (≥ 20) attend to all encoder
  compressed keys, published by layer 20 for the whole prefix, and to only
  the previous 127 decoder inputs. `main` already skips the rows the last
  token does not need, for sweeps of 8192 rows or more.
- **The index batch.** `ds41_index_batch` (~24322):
  - batched top-k starts at `(pos+1)/ratio ≥ 1024`;
  - with batched top-k at layers ≥ 20, a per-row loop still dispatches
    `ds41_attention_candidates` for every row: 3 kernels at layer 20, 1 at
    each layer after it;
  - `ds41_attention_batch` batches key publication only for `ratio == 2`
    (~24374), the Apple-only gate that `1011874` removes.

  `ce5a812` replaces the per-row candidates with a batch that skips rows
  seeing at most 2048 blocks (pos < 16385 × ratio). `3b7f8f2`'s diff context
  is `ce5a812`'s result.
- **The sweep's time.** From Situation 0:
  - a 2048-row sweep from empty takes 14.9-17.9 s: 9-10 s of stages and
    6-8 s of page-in and preparation between layers;
  - later 2048-row tiles of a wide sweep cost about 5 s of stages for all
    40 layers.

  S1a saves the second sweep's page-in. S1b saves decoder-layer tiles. S3
  targets the page-in of single-chunk sweeps.
- **S3's reserve.** The child already reserves 7.12 GiB of prefill headroom
  from the 82 GB target, the same figure as `bac91c2`'s two slots on this
  model. The explicit path replaces the scratch read that warms the file
  cache (`metal_graph_stream_prepare_*`) with reads into the buffers the GPU
  binds.
- **Sections.** `DS41_STAGE` prints `ds4: V4.1 stage layer= pos= rows=
  <label>=<ms>` for seven labels: `hc/engram`, `attention projections`,
  `attention core/index`, `attention output`, `hc/ffn norm`,
  `shared/routed ffn`, `hc expand`. It ends the command batch at each stage,
  so section time is GPU time for that stage.

## Goals / Non-Goals

**Goals:**
- Fewer sweeps and fewer rows per sweep for 3-8K prompts, with bits equal
  to `main` at every harness frontier.
- A faster single-chunk sweep (≤ 2048 rows) through explicit expert buffers,
  if the harness sees it on M5.
- Two kernel steps decided on section time, with the tool that decides them.

**Non-Goals:**
- Token-major tails (frozen by the output rule), the vocabulary-head half
  of `4fbbc4a` (`70`), and the decode path.
- TP, resident mode, `--quality`: S1a's rule is written for every mode and
  keeps each mode's own `minimum`. Only the streaming single-box path is
  measured, though.
- Batched server sessions (`7da9535`).

## Decisions

### D1. Steps and order

S1a → S1b → S2a (`1011874`) → S2b (`ce5a812`) → S2c (`3b7f8f2`) → S3 →
S4.0 (tool) → S4a (#758) → S4b (#864). S1 comes first because it decides
which sweeps are single-chunk, which is S3's domain. S2 follows the PR order,
which `3b7f8f2`'s dependency requires. S4 comes last, since it needs its
tool.

Each step is an uncommitted diff on the branch. Its A tree is
`../sf-ds4-1flash-base` (a detached worktree of `main`) with the previous
steps' diff applied (`git diff main | git -C ../sf-ds4-1flash-base apply`),
rebuilt. The previous step can then be measured without a commit on the
branch.

Alternative: one A/B for S1 as a whole. Rejected. S1b's bitwise proof is
independent of S1a's, and S1b could fail it alone.

### D2. S1a: the tail's own minimum

Keep `798c64f`'s structure in `ds41_prefill_count`: from 3072, a count
capped by `carry_cap`, with the tail kept below 8192. Test the tail against
the `minimum` the *next* call would use, which is the value of the same
function's rules with `pos > 0`. The rule is then an identity: one sweep
exactly where `main`'s second call would be batched with the same rows.

`DS4_METAL_DISABLE_V41_SHORT_SWEEP` (upstream's name) restores `main`'s
schedule. `tests/test_deepseek41_prefill.c` gets its expectations updated.
It also gets one simulation over N = 1..16384 at pos 0 and at pos 2048,
with the streaming and resident minimums, that asserts two things:
- the token-major steps equal `main`'s;
- the sweeps are at most `main`'s.

Alternative: `798c64f` verbatim. Rejected: at pos 0 it batches 5K's
904-token tail, which changes the output.

### D3. S1b: the suffix below 8192, alone

`suffix_rows` and the tile-rounded `first` with 128 warm rows are taken as
in `798c64f`, as upstream text. The encoder-only and resume paths keep their
`!decoder_suffix` refusal. If the harness's `--bitwise` fails at any cold
frontier, S1b is dropped. In that case the `drop: output` goes in the
registry with the frontier that differed.

### D4. S2: three ports, each exact

Upstream text for `ds4.c`, `ds4_metal.m`, `ds4_deepseek41_gpu.h`,
`metal/dsv41.metal` and `tests/test_deepseek41_metal.c`. The CUDA files are
absent: `sf-ablate` is not needed, since they are whole files.

`ce5a812` leaves `block_mask` rows unwritten for rows seeing at most 2048
blocks. Before measuring it, the port reads where `block_mask` is consumed
and records, in the step's short review, that those rows never read it. A
stale mask read is a correctness bug even if the bits happen to match.

### D5. S3: explicit buffers on M5, without the tail cull

Port `bac91c2` + `c12d639`'s `ds4.c`, `ds4_gpu.h` and `ds4_metal.m` hunks
for the buffers, the reader threads, binding, release and the F_NOCACHE
descriptor. Also port their `tests/test_deepseek41_graph.c` cases (the
synthetic-file I/O fixture and the admission and fd tests), as
`test-deepseek41-graph` targets.

Not taken:
- the `moe.metal` tail-cull specializations and their selection in
  `ds4_metal.m`, which are gated on `ds4_gpu_device_is_pre_m5_apple_silicon`;
- the matching `test_metal_moe_prefill` cases.

The device gate on the buffer path is removed rather than widened: the
child is Apple-only, and the owner measures on M5.

The reader count is the existing pool knob, not a new one. The `imatrix`
term is absent in the child.

### D6. S4: sections mode, then two kernels

S4.0 adds `--sections LABEL[,LABEL]` to `ab_bench.py`:
- it sets `DS4_METAL_V41_STAGE_PROFILE=1` for both builds;
- per chunk (layer, pos, rows), it takes the named labels' time divided by
  the other labels' time;
- it pools the ratios by bootstrap 95% CI and reports per rows-shape.

It is a tool step: bitwise, no metric below zero, with `tests/test_ab_bench.py`
cases for the parser and the ratio.

The kernel steps:
- **S4a** targets `attention core/index`. It ports #758 `a3393d7`'s
  `heads16_dual_rb16` kernel (`metal/dsv4_misc.metal`), its pipeline and the
  `prefill_dual_heads_rb16` gate only.
- **S4b** targets `shared/routed ffn`. It puts #864's half LUT into
  `dequantize_iq2_xxs`, with an exhaustive model-less test that compares
  the LUT dequant with the grid dequant for every code.

Each is kept by the context's sections rule, then gets one harness run as
the guard.

### D7. Keep rule, kinds, invocations

Per step, against the previous step, `--bitwise`, `--budget 3600` at most.
A second invocation, pooled with the first, runs unless the first is a drop
or a target's CI lower bound already clears the A/A noise (+1.6%):

| Step | Kinds | Targets |
|---|---|---|
| S1a | `cold-3500,cold-5000,cold-7500,append` | `ttft 3500`, `ttft 7500` |
| S1b | `cold-3500,cold-5000,cold-7500` | `ttft 3500`, `ttft 5000`, `ttft 7500` |
| S2a-c | `cold` | any of the `cold` ttfts |
| S3 | `cold-2500,append` | `ttft 2500`, `append +1500` |
| S4a-b | sections, then `cold` once | section ratio |

Guards on every invocation:
- `--guards guard-decode`;
- `--guards guard-16896` from S1b on, since the decoder-suffix code runs
  there.

The keep and neutral rules are the context's. All steps are under 800
runtime lines. A kept step must also leave the `decode` guard without a
pooled CI wholly below zero. That is S3's known risk (M1's -15% decode).

The first-token details are part of `ttft`, and are reported, not gated. A
step that changes which sweep seeds the decode cache (S1a, S1b) runs with
`--cache-policy-change`: fewer sweeps leave a colder cache by construction.
S1a's first invocation, without the flag, dropped every 3500 and 7500 pair
on "cache state differs" (hits 3801 against 10067 of 19886).

No `--quality` CLI run precedes an invocation (the page-cache trap of `30`).

### D8. Docs, registry, record

Registry:
- #1073: the seven commits' lines, including `ce5a812`'s corrected reach;
- #952: `bac91c2`, `c12d639`;
- #758: the new head;
- #864, #850, #822.

`perf-record.md`: each step's pooled rows, the change's row against the
segment start (`7dea5e3`), and S3's buffer log line.

`AGENTS.md`: the schedule's new shape in "SSD streaming is not optional",
and the new switches (`DS4_METAL_DISABLE_V41_SHORT_SWEEP` and the S3 path's
own switch, if upstream has one) among the knobs.

`speed-bench/README.md`: `--sections`.

## Risks / Trade-offs

- [A wide sweep of 3.5K is not bitwise with two sweeps, e.g. through
  carry-copy or the Engram prefetch] → the harness dumps logits at every
  frontier. S1a is dropped on a mismatch; there is no partial keep.
- [S1b's warm rows round differently (128-row batch vs a 2048 tile)] → the
  same bitwise gate; drop S1b alone.
- [`ce5a812` leaves `block_mask` stale for rows below 16385 × ratio] → D4's
  consumer read before measuring; the unit tests; bitwise at 2.5-10K.
- [S3's F_NOCACHE reads leave the page cache cold for decode misses after a
  prefill] → `decode` guard and the first-token details. If decode drops, try
  the path without `c12d639`'s descriptor, measured as a sub-step.
- [S3's locked 7.12 GiB collides with the dynamic cache] → the admission log
  line must show the dynamic cache unchanged (74.88 GiB, 8078 slots).
- [Sync conflicts in `ds41_prefill_count`, the sweep and the index batch] →
  upstream text wherever it exists, and one adapted expression in D2.
- [A long series of 3600 s invocations] → the order puts the big levers
  first. The steps in S4 can be skipped as history if section time shows
  nothing.

## Migration Plan

Additive and switchable:
- `DS4_METAL_DISABLE_V41_SHORT_SWEEP` and `DS4_METAL_DISABLE_V41_DECODER_SUFFIX`
  restore S1;
- `DS4_METAL_DISABLE_V41_BATCH_*` restore S2;
- S3 falls back to mmap when the buffers cannot be admitted.

Rollback is a revert of the squash commit.
