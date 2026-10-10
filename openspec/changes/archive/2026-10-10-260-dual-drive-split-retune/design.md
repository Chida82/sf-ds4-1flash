# Design

## Context

- `140` admits the copy at engine open (`ds41_prefill_replica_open`):
  - it compares the header and the 43.51 GiB of routed up;
  - it keeps an uncached descriptor (`m->replica_fd`) for the explicit prefill buffers;
  - a `fstat` before each sweep layer stops the prefill if the copy changed.
- Decode misses (`ds4_gpu_stream_expert_cache_begin_selected_load`, every decode layer of the V4.1 graph):
  - one `F_RDADVISE` per family range on `g_model_fd`, the model's cached descriptor;
  - then three whole-family tasks to the 18-thread pool;
  - the reads mostly copy from the page cache the advice filled (`40`: about 20 GB/s either way).
- `PREAD_SPLIT` (4 pieces aligned to 16 KiB) splits only inside `ds4_gpu_stream_expert_pread_tasks`. The early-load path calls `ds4_gpu_stream_expert_pread_pool_begin` directly, so decode misses are not split today: 3.3 tasks per dispatch in the summary.
- `145` S1 put up's whole read on the copy and left its advice on the model: -1.7%.

## Goals / Non-Goals

**Goals:** measure decode misses in pieces, and up from the copy done right, on both APFS and ExFAT; keep output bitwise; change nothing when the switches are off.

**Non-Goals:**
- gate or down from the copy (unchecked bytes);
- the prefill reader share (`140` swept it);
- more than one copy;
- the thread count;
- reading Engram or statics from the copy.

## Decisions

### D1. Pieces in the early-load path

`ds4_gpu_stream_expert_pending_load_add_task` appends one family as `PREAD_SPLIT` pieces, using the same 16 KiB alignment as the existing split, when `DS4_METAL_V41_DECODE_PIECES` is on. The pending load's task array grows to 8 pieces × 3 families × 8 experts, to cover `PREAD_SPLIT`'s upper bound. The thread count follows the task count, at most 18.

### D2. The copy's descriptor for decode

- `ds4.c` reopens the admitted copy by path (`F_GETPATH`) without `F_NOCACHE`, and requires the same device, inode and size as the checked descriptor.
- It hands the descriptor over with `ds4_gpu_set_replica_fd`, -1 when there is no copy.
- A task carries `src` (0 model, 1 copy); the worker resolves the descriptor.
- The readahead takes a descriptor (`ds4_gpu_stream_expert_readahead_range_fd`): up is advised on the drive that will read it. That is the fix to `145`.

### D3. Change check

Before a load that would read the copy, one `fstat` compares size and mtime with the values recorded when the descriptor was handed over. That is about 1 us, about four times a token. On a change, the engine prints once, clears the descriptor, and the misses read the model.

### D4. Last-landing attribution

Each task records its end time. A load that read the copy counts which drive finished last, and the average time of each drive from the pool start. The streaming summary prints `streaming decode replica split loads=.. last_model=.. last_copy=.. model_done_avg=.. copy_done_avg=..`. Balanced counts mean the split is right. A lopsided count says the copy is too slow for up: the next step would be fewer of up's pieces.

### D5. Switches

`DS4_METAL_V41_DECODE_PIECES` and `DS4_METAL_V41_DECODE_REPLICA_UP` are read per load: set and not "0" means on. That lets `--decode-switch` flip them between sessions.

### D6. Evidence and order

1. `make test`; `make test-deepseek41-decode-switch` for each switch, bitwise, with `DS4_METAL_PREFILL_REPLICA` set so the copy is admitted; `make test-deepseek41-prefill-replica REPLICA=<path>`.
2. Harness `decode,append`, `--bitwise`, 3600 s, the copy admitted on both sides (`--env`), on the drive's current file system:
   - B = pieces;
   - B = up from the copy;
   - B = both.

   A = the same tree with the switches off.
3. Reformat the drive, copy the GGUF, and repeat the two copy steps. The pieces step does not read the copy, so it runs once.
4. The keep rule: a decode CI above zero, no other headline below -0.2% with its CI below zero, bitwise.

## Risks / Trade-offs

- **The copy's pages enter the page cache.** Decode reads it through a cached descriptor, like the model. `250`'s residency probe and the first-token figures tell whether that costs the statics.
- **Pieces raise the queue depth on the internal drive,** which also serves Engram during decode. The `decode` kind measures the net effect.
- **One miss split over two drives can fail on one.** The load fails as any failed read does today, and the engine reports it.
- **Thermal drift across the night.** Each A/B pairs A and B inside one invocation; comparisons across file systems use gains, not absolute rates.

## Migration Plan

Branch `perf/260-dual-drive-split-retune` from `main`; the worktree is `../sf-ds4-1flash-260`. The switches stay off by default. A kept step becomes the default only by a later decision, and only when the copy is admitted. No commit or push without a request.
