# Design

## Context

- `140` admits the copy at engine open (`ds41_prefill_replica_open`: header and 43.51 GiB of routed up compared) and keeps its fd in the model (`m->replica_fd`); before each layer read a `fstat` checks size and mtime, so a copy changed while running stops the prefill.
- The explicit buffers read a layer with 8 workers; 3 read `up` from the copy, 5 read gate/down from the model.
- Decode misses: `ds4_gpu_stream_expert_cache_load_selected_missing` builds `pread` tasks, 4 pieces aligned to 16 KiB per family range (`DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT`), run by an 18-thread pool on `g_model_fd`. The tasks are joined before the expert pass.
- `145`'s split variant read all of `up` from the copy (family split); it is the k = 4 column of the gate table.

## Goals / Non-Goals

**Goals:** a measured best split for decode misses and prefill on a box with one external drive; output bitwise; no effect when the copy is not admitted.

**Non-Goals:** more than one replica (three-drive weights), reading Engram or statics from the copy, prefill through mmap from the copy (a `250` note), changing the pool's thread count or piece size.

## Decisions

### D1. Split unit: pieces, chosen by a fixed pattern

Decode misses split by pieces, not by family or expert: the gate table gives the latency per k, and pieces keep every read's alignment and size. A fixed pattern (every m-th piece of the expert's 12 to the copy) is deterministic and needs no per-read state. Alternative, Argodrive's byte weights per source: equivalent at this granularity, with more code.

### D2. The copy's descriptor

The Metal side receives the copy's fd from `ds4.c` when `140` admits it, through a setter like `ds4_gpu_set_model_fd`. It is opened by `140` with caching as decode needs; a pool task carries which descriptor to read. If the copy fails the per-sweep `fstat` check, `ds4.c` clears the Metal fd and decode reads only the model.

### D3. Last-landing attribution

Each load records which descriptor's piece finished last. The streaming summary prints `replica split: k=.., last internal .. / copy ..`. A share is right when the two counts are close; a lopsided count says which way to move k.

### D4. Prefill share

`DS4_METAL_PREFILL_REPLICA_READERS=n` sets how many of the 8 workers read from the copy; up first, then gate if n exceeds up's share of the bytes. Default stays 3 until a CI above zero on ttft says otherwise.

### D5. Evidence

- `make test`, `make test-deepseek41-prefill-replica REPLICA=<path>`, the decode-switch test with the split on and off (bitwise), `test-metal-ssd-experts`.
- Harness `decode,append` with the guards, `--bitwise`, B with the split, the copy admitted on both sides; then `cold,append` for the prefill share. One row per step, with the last-landing counts.

## Risks / Trade-offs

- The copy's latency floor survives on APFS -> the gate closes S1 before any code.
- The copy's drive is also the KV directory when `160`'s placement is used -> measured with KV on the internal drive; a note says what changes when both share the drive.
- Bus contention on Thunderbolt during prefill -> the S2 sweep decides.
- A miss split over two drives fails on one -> that piece is re-read from the model, counted.

## Migration Plan

Branch `perf/260-dual-drive-split-retune` from `main` after `250`. Default off until measured; a kept split becomes the default only when the copy is admitted. No commit or push without a request.
