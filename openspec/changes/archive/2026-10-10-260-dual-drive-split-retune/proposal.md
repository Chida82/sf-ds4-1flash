# Proposal

## Why

With one external drive, the Argodrive fork measured steady decode at 18.66 tok/s on the internal SSD alone, 21.05 with one enclosure (+12.8%) and 22.25 with two (V4.1 Q4, pp512). Their decode reads split each miss across the drives by weight (`DS4_ARGODRIVE_DECODE_WEIGHTS`).

Here the idea measured -1.7% on decode (`145`, ExFAT). Reading the code shows that `145` tested one variant, and one that could not win:
- Decode misses go through `ds4_gpu_stream_expert_cache_begin_selected_load`. It advises each family range with `F_RDADVISE` on the model's cached descriptor, then hands the pool **three whole-family reads** (2.9, 2.9 and 3.7 MiB). The 4-piece split (`DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT`) only applies in `ds4_gpu_stream_expert_pread_tasks`, which this path skips. The streaming summary confirms it: 3.3 tasks per dispatch, against 12.8 when `40` measured the split.
- `145`'s S1 moved only the up `pread` to the copy. The readahead stayed on `g_model_fd`, so the internal drive most likely still read up into the page cache, and the copy read it again as one 2.9 MiB request at queue depth 1. (The code was reverted and is not in git.)

What was never measured:
- decode misses in pieces, on the internal drive alone, since the early-load path took over;
- up from the copy with its readahead on the copy;
- up from the copy in pieces.

The file system can matter here: the decode path relies on `F_RDADVISE` and the page cache. APFS is a kernel file system. ExFAT on this macOS runs in user space (FSKit), so every request crosses to another process, and whether `F_RDADVISE` starts an asynchronous read there is unknown. `250` measured the copy delivering up's 2.9 MiB in 4 uncached pieces in 0.634 ms on APFS, against 0.69-0.74 ms on ExFAT in another session.

Ceiling: a layer with a miss costs the main thread about 0.45 ms of preparation (three `F_RDADVISE` calls make most of it) and 0.66-0.70 ms of wait, about 1.1 ms × 3.8 layers per token, about 10% of a token. Taking 30% off the read and leaving the 20-28% of misses served by the page cache gives about 1.3-1.5% of decode.

## What Changes

- **S0, gate.** Two probes on both file systems, the same night:
  - `missbench`: uncached pieces, from `250`;
  - `enginebench`: the engine's path, with cached descriptors, `F_RDADVISE` in series, the reads at once, and only experts with no resident page.
- **S1a, decode misses in pieces.** `DS4_METAL_V41_DECODE_PIECES=1` splits each family of a decode miss into `PREAD_SPLIT` pieces (4 by default), so the pool reads up to 12 at once. It does not need the copy.
- **S1b, routed up from the copy.** `DS4_METAL_V41_DECODE_REPLICA_UP=1`. A decode miss reads routed up from the copy admitted by `140`, through a second, cached descriptor, with its `F_RDADVISE` on the copy. It combines with S1a.
  - The copy's size and mtime are checked once per load; a change sends the misses back to the model.
  - The streaming summary counts which drive's last piece landed last.
- Both switches are read per load, off by default, and bitwise by construction: the same bytes land in the same slots.
- **Dropped: the prefill share (old S2).** `140` already swept 2, 3 and 4 of 8 readers with the same wait; the enclosure's 6.4 GB/s sets it. `250` measured the same prefill gains on APFS and ExFAT.
- **Out of scope: gate or down pieces from the copy.** `140` checks only routed up, so any other byte read from the copy is unverified. Widening the check costs about three times its 7 s per open, unless `265`'s stamp makes it a one-time cost.
- Every harness step runs on both file systems. The choice of file system weighs this change's decode gain against the first token after a long prompt, which `250` found 0.36 s better with ExFAT.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`:
  - a source per `pread` task, plus the copy's descriptor;
  - readahead on a chosen descriptor;
  - decode misses split into pieces in the early-load path;
  - last-landing counters.
- `ds4.c`: a cached descriptor on the admitted copy, handed to Metal.
- `ds4_gpu.h`: `ds4_gpu_set_replica_fd`.
- If kept:
  - `AGENTS.md`: the split sentence, which is wrong for decode today, and the switches;
  - the README's second-drive section;
  - `docs/upstream-prs.md` (`DS4_ARGODRIVE_DECODE_WEIGHTS`);
  - `speed-bench/perf-record.md`.
- Needs the external drive for S1b, reformatted between file systems during the session.
