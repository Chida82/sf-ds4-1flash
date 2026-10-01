# Proposal

## Why

For the owner's prompts (1-10K tokens), the time to first token is:

`(sweeps × the time of one SSD layer sweep) + (token-major tail steps × the time of one decode step)`

`ds41_prefill_count` (`ds4.c` ~24625) sets that shape. Take a cold prompt of N
tokens with our fixed 75 GiB cache (8078 slots, at least half the experts):

- the first call returns the last multiple of 2048 at or below N if N ≥ 4096,
  and otherwise at most 2048;
- at pos > 0 a remainder under 1024 tokens runs token by token, at the
  decode rate (about 45 ms a step after `40`);
- a remainder of 1024 or more costs a second full sweep. A 2048-row sweep
  from empty takes 15-18 s, and 6-8 s of that is layer page-in and
  preparation outside the GPU stages (`perf-record.md`, Situation 0).

Examples:

| Prompt | Cost on `main` |
|---|---|
| 2.5K | 1 sweep + 452 token-major steps |
| 3.5K | 2 sweeps |
| 5K | 1 sweep + 904 token-major steps |
| 7.5K | 2 sweeps |

The no-output-change rule freezes the token-major tails, because batched and
token-major kernels round differently. That leaves three levers:

- fewer sweeps, wherever the result stays bitwise;
- less work inside a sweep, where it stays bitwise;
- faster sweeps and kernels.

## What Changes

- **S1a, one sweep instead of two, bitwise subset only.** Take the
  `ds41_prefill_count` half of #1073's short sweep: `4fbbc4a`'s sweep half,
  then `ccbf2c0`, `64240fb` and `798c64f`, whose net is `798c64f`'s state.
  - A 3072-8191-token remainder runs as one wide sweep only where `main`
    would batch its tail: the tail is 0, or at least the minimum `main` uses
    at pos > 0 (1024 here).
  - The row partition stays the same 2048-row tiles, so the output must be
    bitwise identical to `main`.
  - `798c64f` tests the tail against the pos-0 minimum (256), which would
    batch 5K's 904-token tail. That part is `drop: output`.
  - Expected: one sweep less for 3.5K and 7.5K, and the same path for 5K
    [inferred].
- **S1b, the decoder suffix from 2541 rows.** Take the rest of the same
  commits: below 8192 rows, a wide sweep runs layers 20-39 only on the rows
  the last token depends on. The first row is rounded down to a 2048 tile and
  128 rows are warmed, which keeps `main`'s partitions.
  - Proven bitwise on its own, or dropped.
  - Expected: layers 23-39 skip one or more 2048-row tiles for 4-8K sweeps
    [inferred].
- **S2.** #1073 prefill index batching, in the PR's order, each as its own
  step, exact per its unit tests and bitwise on the model:
  - `1011874`: batched ratio-1 key publication (drops the Apple-only
    `ratio == 2` gate);
  - `ce5a812`: batched candidate blocks. The registry said "above 16K
    only", but in the child the per-row candidate loop runs for every row of
    a batched top-k at layers ≥ 20. The commit replaces that loop and skips
    rows that see at most 2048 blocks, so it reaches 2-10K prompts too;
  - `3b7f8f2`: select-all for rows with at most 512 visible keys, plus a
    batched top-k from 512 visible keys instead of 1024. It is built on
    `ce5a812`.
- **S3.** #952 `bac91c2` + `c12d639`, explicit expert buffers only:
  - each layer's experts are read into two locked Metal buffers inside the
    existing 7.12 GiB two-layer prefill reserve, and the next layer's read
    overlaps the current layer's compute;
  - only for single-chunk sweeps of 32-2048 rows (cold ≤ 2.5K, appends of
    1024-2047), with F_NOCACHE reads on a separate descriptor;
  - the pre-M5 gate is widened to M5;
  - about 370 runtime lines, so the CI rule applies;
  - claim: M1 Max 32 GB, 1241 tokens, prefill 11.4 -> 49.9 t/s,
    byte-identical logits. Not taken: its tail-cull MoE kernels, which are
    gated to pre-M5 and never run on the measuring box.
- **S4, kernel steps under the harness's resolution**, decided on GPU section
  time (`DS4_METAL_V41_STAGE_PROFILE`):
  - first, a tool step that adds the sections mode to `ab_bench.py`;
  - #758, now at head `a3393d7`: the `heads16_dual_rb16` kernel and its
    gate only (≥32 rows, "M5 Max"), bitwise. Its `topk_fused512` is not
    reachable from V4.1: the indexer top-k is causal;
  - #864 `482e246`, IQ2_XXS half LUT only. Its 2048 entries equal 0.25 ×
    grid exactly, but fast-math means it still needs an exhaustive dequant
    equality test and on-device bitwise output.
- **Not taken:**
  - `drop: output`: batching a short tail from the pos-0 minimum (above);
    `7da9535`, `4b1b151` and `af7c02b`; #864's split MPP (a different
    accumulation);
  - not measurable here: #952's pre-M5 tail-cull kernels;
  - not reachable from V4.1: #850, #822, and #758's fused top-k.

## Capabilities

### New Capabilities
None. Output is bitwise identical (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`:
  - S1: `ds41_prefill_count` and `ds41_graph_prefill_sweep`;
  - S2: `ds41_index_batch`, `ds41_attention_batch` and the graph buffer
    table;
  - S3: the streaming prefill buffers.
- `ds4_metal.m`, `ds4_gpu.h`, `metal/dsv41.metal`: the S2 kernels and the S3
  buffer binding.
- `metal/dsv4_misc.metal`, `metal/moe.metal`: S4.
- Tests: `tests/test_deepseek41_prefill.c` (the schedule's expected counts),
  `tests/test_deepseek41_metal.c` (S2), `tests/test_deepseek41_graph.c` (S3),
  and a dequant test (S4).
- Judged on the `cold` group and `append`. `decode` and `guard-16896` are
  guards.
- Registry lines: #1073 (7 commits), #952 `bac91c2` `c12d639`, #758 (new
  head), #864, #850, #822.
