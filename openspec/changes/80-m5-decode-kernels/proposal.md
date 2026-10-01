# Proposal

## Why

After the decode fusions in `70`, large dense projections may dominate the remaining token time: the Q2 GGUF's q_b/output_a/output_b families alone occupy 4.65 GiB, against 2.22 GiB of selected routed weights per token. `docs/MacM5.md` establishes the M5 Max's bandwidth opportunity, not an achieved kernel rate; a fresh post-70 profile must establish the target.

## What Changes

- Start after `60` and `70` are resolved and their kept work is available in the baseline. A closed performance gate is a valid outcome, not permission to implement another idea.
- Reuse the encoder timeline and uninstrumented harness to distinguish dense matvec time, index scoring, CPU gaps and reads.
- Tune independent output-row grouping and input reuse for V4.1's live Q8 decode projections, preserving each row's K walk, reduction tree and BF16 boundaries, including the kernels selected after `70`.
- Independently evaluate row-locality changes to the live 32-head indexer scorer, without replacing its arithmetic or top-k tie order.
- Keep only bitwise, independently measured wins; no speculative decoding, new quantization, batch schedule change or CPU/ANE offload.

## Capabilities

### New Capabilities
None. Internal exact kernel optimization only (`skip_specs: true`).

### Modified Capabilities
None. The existing `perf-harness` contract is used unchanged.

## Impact

- `metal/dense.metal`, `metal/dsv4_misc.metal`, relevant post-70 producers in `metal/dsv41.metal`, dispatch selection in `ds4_metal.m`; narrow test hooks in `ds4_gpu.h` only if needed.
- Existing Metal/graph tests, the performance record and registry verdicts when acting on an upstream commit. No new framework or dependency.
- Registry constraints: #1061 and #1073's changed-reduction scorers remain rejected; #959 is not ported on a long-context claim alone. #1073 remains owner of the inherited decode-glue region.
- Later changes execute in numeric order, one branch at a time. They build on kept results, not on the assumption every proposal will succeed.
