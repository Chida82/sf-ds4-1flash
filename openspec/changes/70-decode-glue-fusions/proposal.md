# Proposal

## Why

V4.1's single-token graph mirrors the reference model op by op: about 59
dispatches per layer of HC, router, shared-expert, rounding and small attention
kernels (#1073's count). Under SSD streaming this glue runs in series with the
expert reads and cannot hide behind them.

Two open upstream PRs fuse the same sites while keeping the arithmetic, so
only one of them can own this code zone:

| | #1073 (chosen) | #1042 (`history`: the alternative) |
|---|---|---|
| Base | merged with `0aaea5a`, mergeable | 75 commits behind; applies with 2 conflicts |
| Router | `edceb7ab`, with main's current softplus | stale softplus, and a tie order from #832 that is not in main: not exact against the child |
| Shape | small separable commits, then `d8d1523b` | 7 commits, about 1.6K lines |
| Claimed decode gain | about 59 -> 17 dispatches per layer; +5-9% estimated here | +3-6% estimated here |
| Catch | `d8d1523b` interleaves DSpark code, so it needs a manual port | the router must be replaced (#1090's) |

Both were measured only resident, on M3 Ultra or M4 Pro, so bitwise identity
on M5 is unproven.

## What Changes

- **Start gate.** This change starts only if `20`'s baseline decomposition
  (`DS4_METAL_GPU_BUSY_PROFILE`), re-read after `30`, shows the per-layer glue
  as a meaningful share of the token. Otherwise it waits in `history` until
  upstream merges #1073.
- **Steps, one commit each, each judged against the previous one:**
  - S1 `e7683961`: skip candidate selection while every block is kept
    (exact up to 2048 blocks).
  - S2 `4fbbc4a4`, head part: encode the vocabulary head before the last
    drain. It builds on `30`'s queue.
  - S3 `edceb7ab`: select experts in one dispatch. It must match the bitonic
    order on ties; test with forced ties and an all-equal round.
  - S4 `d95f8b61` + `1923131d`: BF16 rounding inside the producing kernels;
    the rope contraction matches the fused store.
  - S5 `d8d1523b`, without DSpark. More than 800 lines, so it needs at least
    +1.5% decode.
    - It covers: HC block input in one dispatch; paired Q8_0 projections and
      norms; q_b with RoPE; RoPE + quantize + store; staged attention gather;
      low projection with inverse RoPE; output and shared down fused into the
      HC expand; shared gate/up SwiGLU; asynchronous Engram start/finish.
    - It is a manual port. If the fusions cannot be separated cleanly from the
      DSpark code, S5 is dropped and recorded.
- **Bitwise proof on M5 for every step**, before the harness:
  - `make test-deepseek41-metal`;
  - #1073's `--decode-switch` harness (`a3f6f313`), run with `--ssd-streaming`
    and the fixed cache;
  - rounds with zero and −0 residuals, NaN/Inf/denormals, and all logits at
    −120 (the polynomial softplus branch).
- **Not taken:**
  - `drop: output`: #1073 `262b4a66` and `a6b50ff6`, whose MMA rows round
    differently;
  - never: the DSpark commits;
  - `history`: #1042 and #1090.

## Capabilities

### New Capabilities
None. Output is bitwise identical (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: the ds41 decode graph. `ds4_metal.m`, `metal/dsv41.metal`,
  `metal/dsv4_hc.metal`, `ds4_deepseek41_gpu.h`, `tests/test_deepseek41_metal.c`.
- A large, permanent conflict surface until upstream merges #1073. Accepted
  by the owner's rule: open PRs are ported when they pass the threshold.
- Judged on `decode` and `append` (the token-major tails); `cold` is a guard.
- Registry lines: #1073 (7 commits, plus the DSpark and MMA exclusions), #1042,
  #1090.
