# Proposal

Gated on `780-v41-append-selected-experts-evidence`: this change starts only
after `780` records `GO` in `speed-bench/perf-record.md`.

## Why

A chat-turn append of 256-1000 tokens is one layer sweep, and that sweep
costs 6.0-6.7 s whatever its length (perf-record, 770). The time is expert
delivery: each layer fills its explicit buffer with all 384 routed experts
(3.56 GiB), about 44% blitted from the decode cache and 56% read from the
SSD at the drive's rate (perf-record, 100: "what remains of the wait is
bandwidth"). The GPU work of 300 rows is a small part of the 155 ms a layer
takes.

The rows of a short sweep select only part of a layer. The estimate from
recorded data (`310`: one extra row costs +5 expert misses over 40 layers at
`82GB`) is that a 300-row append needs under 40 of the roughly 184 uncached
experts of a layer; `780` replaces this estimate with counts. Reading and
copying only what the rows selected would then take a 300-row sweep from
about 6.3 s to an estimated 2.5-4.5 s. On a typical turn (300-500-token
append, 500-token answer) that is an estimated 8-15% end to end, 3-5% with a
2000-token answer, and nothing for cold prompts.

The routed kernels already index weights only by the selected ids, so the
output does not depend on what the other experts' bytes are.

## What Changes

- For a sweep of one tile whose row count is at most a limit, each layer
  runs its attention and its router first, reads the selected ids, and
  delivers to the layer buffer only the experts at least one row selected:
  blitted from the decode cache when it holds them, read from the SSD (and
  the replica, when configured) when it does not. Then the layer's experts
  run as today.
- Larger sweeps, sweeps of several tiles, and sweeps without the explicit
  buffers keep today's whole-layer delivery with its read-ahead.
- `DS4_METAL_V41_SELECTIVE_SWEEP_MAX=<rows>` (tuning) sets the limit; `0`
  restores whole-layer delivery everywhere. The default is the measured
  break-even.
- `DS4_METAL_V41_SELECTIVE_SWEEP_POISON=1` (test) overwrites every
  undelivered expert of a layer buffer before the layer computes, so a test
  proves no kernel reads them.

## Capabilities

### New Capabilities
- `prefill-expert-delivery`: which routed experts a prefill sweep delivers to
  its layer buffers. (`780` creates the capability with the report; this
  change adds the delivery rule.)

### Modified Capabilities
None.

## Impact

- Code: `ds4.c` (`ds41_moe_batch` split in two, `ds41_graph_prefill_sweep`,
  `ds41_prefill_expert_read_start`), `ds4_metal.m` and `ds4_gpu.h`
  (`ds4_gpu_stream_prefill_copy_cached` takes a mask), `ds4_env.def`,
  `tests/test_deepseek41_graph.c`, `Makefile` (one model-backed target).
  Expected under 300 runtime lines.
- Output: bitwise identical. Same kernels, same weights for every expert a
  row uses; only bytes no kernel reads differ.
- Cache: the seed after a sweep takes selected experts only, and all of them
  are delivered, so the decode cache should end in the same state. The bytes
  read fall, which the harness's cache-state check reports.
- Speed: `append +300` and the `short` kinds (512-row appends) gain;
  `append +1500`, `cold-*` and `decode` must not move.
- Docs: `AGENTS.md` (prefill paragraph), `speed-bench/perf-record.md`,
  `docs/upstream-prs.md` (`ee7e840` and #454 lines point here).
