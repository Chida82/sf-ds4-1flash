# Proposal

## Why

Per the code model, expert miss service is the largest term of a streaming
decode token, and of every token-major prefill step. [inferred; `20`'s
baseline decomposition confirms or corrects it]

- Each missing expert costs about 9.5 MiB of `pread`, issued by a 9-thread
  pool with one task per expert tensor (`ds4_metal.m` ~12226, ~12493).
- The reads run in series with the GPU work of the layer. The hits-first split
  fires only with 3 or more misses in a layer.
- A 75 GiB dynamic cache holds about 53% of the 142 GiB of routed experts.

Three things are missing:

- **Pool visibility.** The child cannot show how deep the read queue is, or
  what bandwidth the pool reaches. So it cannot tell a latency-bound read
  path from a bandwidth-bound one, and every later I/O decision depends on
  that.
- **Robust loading into a full cache.** A fixed cache is always full. #952
  `a2e2ea53` fixes four failure modes on that path: the service thread
  waiting on GPU work, allocation past the budget, a non-atomic `done_seq`,
  and lost slab slots.
- **Read-shape tuning.** #621 `8f5a7458` splits each expert read into 16 KiB-aligned
  pieces on the same pool, to raise the NVMe queue depth. It measured +16%
  decode on an M1 Pro, bit-identical by construction. Several existing
  switches (`DS4_METAL_STREAMING_EXPERT_PREAD_THREADS`,
  `DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD`,
  `DS4_METAL_DISABLE_STREAMING_EXPERT_SLABS`, `DS4_METAL_STREAMING_EXPERT_SLAB_MB`)
  have never been measured on this machine.
  - #533 found that the read-ahead hints, issued on the eval thread, cost
    +13% on GLM streaming, but withdrew the change after an M5 Pro prefill
    regression. That is exactly the kind of result this machine must settle
    for itself.

## What Changes

- **S0, tool.** #570 `a1afb82`: pool dispatches, average queue depth, pool GB/s
  and task GB/s in the timing summary.
- **S1, correctness.** #952 `a2e2ea53`, judged by the tool/correctness rule:
  bitwise output, no metric below zero.
- **S2, switch sweeps, no code.**
  - Pread threads at 4, 9 and 18; read-ahead on and off; slabs on and off;
    slab size.
  - A non-default setting that wins by the keep rule becomes the default,
    which is a constant change.
  - Read-ahead is judged on the decode *and* the cold-prompt kinds, because
    #533's regression was in prefill.
- **S3.** #621 `8f5a7458` with the measured best split as the default; then
  #621 `f7695ea0` (an `F_NOCACHE` descriptor for expert reads) as its own
  step. Same bytes are read, so both are bitwise by construction.
- **S4, conditional.** #1033 `66f757b`, which attaches the owned slabs to a
  Metal residency set (53 runtime lines).
  - It starts only if `DS4_METAL_CB_TIMES` shows a submission delay per
    command buffer. With about 81 buffers per token, even a partial cost
    matters.
  - It becomes the default only if it wins. Its macOS-version dependence is
    recorded.
- **Not taken.**
  - #848: `drop`. Its packer zeroes the GGUF expert space that the prefill
    sweep still maps, and it needs a 142 GiB sidecar.
  - #1035: superseded. The child already reads the Engram with 16 workers.
  - #499: already in main (static weights locked).
  - #725, #454, #1117: `drop` / `not reachable`.
  - #647, #739, #738: CUDA. The Metal cache already has per-(layer, expert)
    hotness plus LRU, and unified memory has no upload step.
  - #570 `66ca6ef` (I/O tier pin): `drop`, neutral in the foreground.

## Capabilities

### New Capabilities
None. Output is bitwise identical; the pool stats are diagnostics
(`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: streaming expert cache (pread pool, slab allocation, service
  thread, loader). No kernel change.
- Every step is judged on the `decode` and `append` kinds (token-major tails),
  with the cold kinds as guard. Expert-cache hit counts must match between A
  and B, since no step here changes the replacement policy.
- Registry lines: #570, #952 `a2e2ea53`, #621, #1033, #848, #1035, #499, #725,
  #454, #533, #1117, #647, #739, #738.
