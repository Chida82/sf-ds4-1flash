# Proposal

## Why

Upstream `64ceeea` (merged, in `b3f5018`) scores long V4.1 decode index rows
from a bf16 copy of the index keys. The keys are FP4 values on a power-of-two
scale, which bf16 holds exactly, so the copy halves the bytes the scorer reads
and the bits do not change. The registry filed it under prefill-side
long-context work (`history: long`), but it is decode-side: from 8192 index keys
(about 32K tokens of context) every index-source layer of every decode token
reads the whole key cache. Change `690` took the rest of upstream's long-context
indexer and measured decode +2.6% / +4.1% after 40K / 72K tokens; this is the
part of upstream's line it left out.

## What Changes

- Every kernel that writes the index keys also writes a bf16 copy (one per
  key-owning layer), and decode scores from the copy once there are 8192 keys
  or more, with upstream's scorer kernels (split-4 below 10240 rows, split-2
  below 65536, two keys per thread above).
- A restored session rebuilds the copies; a restored key that is not exact in
  bf16 makes decode score the f32 keys, with a one-line notice.
- `DS4_METAL_DISABLE_V41_INDEX_BF16=1` skips the copy, as upstream.
- No output change.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `long-context-index` (from `690`): long index rows scored from exact bf16
  keys.

## Impact

- Code: `ds4.c` (graph buffers, producers, restore), `ds4_metal.m`,
  `metal/dsv4_misc.metal`, `ds4_deepseek41_gpu.h`, `ds4_env.def`.
- Memory: 256 bytes per index key per owner (2 MiB per owner at 32768 tokens
  of context, 16 MiB at 262144).
- Tests: upstream's bf16-view check in `tests/test_deepseek41_metal.c`; a
  session save/restore check of the fallback.
- Depends on `690` (the long-context index it modifies).
