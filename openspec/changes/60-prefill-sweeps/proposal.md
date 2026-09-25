# Proposal

## Why

For the owner's prompts (1-10K tokens), the time to first token is:

`(sweeps × the time of one full SSD sweep) + (token-major tail steps × the time of one decode step)`

`ds41_prefill_count` (`ds4.c` ~24610) sets that shape. Take a cold prompt of N
tokens with a cache of at least 7680 slots, which is our fixed 75 GiB case:

- one sweep covers up to the last multiple of 2048;
- a tail under 1024 tokens then runs token by token;
- a longer tail costs a second full sweep, which re-reads about 142 GiB of
  experts.

Examples:

| Prompt | Cost |
|---|---|
| 3.5K | 2 sweeps |
| 5K | 1 sweep + 904 token-major steps |
| 7.5K | 2 sweeps |

The no-output-change rule freezes that policy, because batched and token-major
kernels round differently. That leaves three levers:

- fewer sweeps, wherever the result stays bitwise;
- faster sweeps;
- cheaper prefill compute.

Token-major tails get faster through `30`-`50`.

## What Changes

- **S1, one sweep instead of two, bitwise subset only.** Adapt #1073
  `ccbf2c08`, `64240fb9` and `798c64f4` so that a 3072-8191-token prompt runs
  as one sweep whenever main would already batch its tail (a tail of 1024 or
  more at pos > 0).
  - The row partition stays the same (the same 2048-row chunks), so the
    output must be bitwise identical to main.
  - Prompts whose tail main runs token by token keep main's path; the PR's
    change there is `drop: output`.
  - Proof: bitwise logits against main on cold 3.5K, 5.5K and 7.5K prompts,
    and an unchanged path on 5K and 6.5K.
  - Expected: one full sweep less for about half of the 3-8K prompts
    [inferred].
- **S2.** #1073 prefill index batching, each as its own step, exact per its
  unit tests:
  - `10118742`: batched ratio-1 key publication;
  - `3b7f8f22`: select-all for rows with at most 512 visible keys;
  - `ce5a812f`: batched candidate blocks. It applies only above 16K, so it
    is judged on the guard kind.
- **S3.** #952 `bac91c21` + `c12d639a` (849 lines, so at least +1.5% TTFT):
  - each layer's experts are preread into two locked Metal buffers, and the
    next layer's read overlaps the current layer's compute, for single-chunk
    sweeps up to 2048 tokens;
  - its pre-M5 gate is widened to M5;
  - claim: M1 Max 32 GB, a 437-token prompt goes from 4.05 to 14.7 t/s with
    byte-identical text. It must be proven bitwise here.
- **S4, small kernel steps under the harness's resolution**, decided on GPU
  section time (`DS4_METAL_V41_STAGE_PROFILE`), as `sf-q3-8flash` does:
  - #758 `e154aa8`, rb16 hunk only, ported by hand (dual-heads indexed
    attention at ≥32 rows, bitwise);
  - #864 `482e246`, IQ2_XXS half LUT only. Its 2048 entries equal 0.25 × grid
    exactly, but fast-math means it still needs an exhaustive dequant
    equality test and on-device bitwise output.

  The first S4 step adds the sections mode to `ab_bench.py` as a tool step.
- **Not taken:**
  - `drop: output`: #1073's short sweep over token-major tails, `7da9535f`,
    `4b1b1519`, `af7c02b5`; #864's split MPP (a different accumulation);
  - `not reachable from V4.1`: #850, #822.

## Capabilities

### New Capabilities
None. Output is bitwise identical (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: the V4.1 session prefill loop and `ds41_prefill_count` (S1), and
  the ds41 prefill index paths (S2). `ds4_metal.m` and `ds4.c`: streaming
  prefill buffers (S3). `metal/moe.metal` and the indexed-attention kernel
  (S4).
- Judged on the `cold` and `append` kinds; `decode` and the 16K prompt are
  guards.
- Registry lines: #1073 (6 commits), #952 `bac91c21` `c12d639a`, #758, #864,
  #850, #822.
