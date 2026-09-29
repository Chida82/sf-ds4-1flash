# Proposal

## Why

`20` read the 38 ms of `sync` in a 56 ms decode token as the wait for
missing experts' loads. S0 of this change measured it again: `sync` is GPU
work and does not grow with misses; the reads and buffer preparation are
about 4 ms of a 52 ms token (`speed-bench/perf-record.md`, Read path). The
change keeps its correctness fixes and the knobs that can reach those 4 ms
or the per-submission cost inside `sync` (design D7).

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
- **Robust loading into a full cache.** A fixed cache is always full. #1125
  (four commits) returns slab slots on every load error path, marks GPU-copy
  entries in flight until their blit runs (the V4.1 prefill seed takes that
  path), keeps the per-layer counts true, and stops `prune_global` spinning
  on an in-flight entry. #952 `a2e2ea53` overlaps it: its slot return is the
  same fix in the same function, and the rest (the service thread waiting on
  GPU work, allocation past the budget from the worker, a non-atomic
  `done_seq`) serves the `metal_graph` async load worker, which V4.1 never
  runs.
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
  and task GB/s in the timing summary. `ab_bench.py --b-env KEY=VALUE`, so a
  switch can be measured on one tree.
- **S1, correctness.** #1125's four commits, judged by the tool/correctness
  rule: bitwise output, no metric below zero. #952 `a2e2ea53` is not taken.
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
- **S4.** #1033 `66f757b`, which attaches the owned slabs to a Metal
  residency set (53 runtime lines), measured directly with `--b-env`.
  `DS4_METAL_CB_TIMES` cannot gate it: it waits on every command buffer, so
  it hides the submission cost it would have to show. It becomes the default
  only if it wins; otherwise it is reverted. Its macOS-version dependence is
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
- `speed-bench/ab_bench.py`: `--b-env`.
- Registry lines: #570, #1125, #952 `a2e2ea53`, #621, #1033, #533 (the lines
  of #848, #1035, #499, #725, #454, #1117, #647, #739 and #738 already record
  their verdicts and stay).
