# Design

## Context

- The copy is read by `140`: the explicit prefill buffers read routed `up` from it on 3 of their 8 readers and gate/down from the model; the engine open compares the header and the 43.51 GiB of routed up (about 7 s on ExFAT).
- Decode never reads the copy. The pool reads misses from the model in 4 pieces on 18 threads (`DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT`, `_PREAD_THREADS`). `145` measured 4.0 miss layers per token, `pread` 0.667 ms per miss layer: about 7% of a 38 ms token.
- The ExFAT figures to compare against are in `perf-record.md`: Dual-drive prefill after 132, Decode misses after 140, KV cache placement after 150, External SSD evidence after 170, Dual-drive port to upstream ds4.

## Goals / Non-Goals

**Goals:** the same measurements on APFS, with the same harness settings, so each ExFAT row has an APFS row beside it; a stated answer to "was the floor the file system?".

**Non-Goals:** any runtime change, tuning the split (that is `260`), the Engram copy (`150` found the sweeps wait 0.00-0.03 s on Engram with the copy; the file system cannot move that), upstream ports.

## Decisions

### D1. Order and conditions

1. Copy latency probe: minutes, no model load; first, because it decides `260`.
2. Harness runs (`cold,append`, then `decode`), on a quiet machine at pressure Nominal at start, the usual budget.
3. KV and mmap probes last.

Every run notes the thermal state, like the other rows.

### D2. The latency probe

Rebuilt from the description in `145` (the original `missbench` lived in a scratchpad that is gone): random layer and expert, 300 alternated iterations per mode, `F_NOCACHE` on both descriptors so neither page cache serves the reads; median, p10 and p90 per cell. A second table adds pieces of gate and down from the copy, so `260` can choose among family, piece and expert splits.

### D3. What counts as "the floor moved"

The copy's single-piece median for 2.2-2.9 MiB falls below the internal drive's median for the remaining pieces of the same expert. Only then can a split shorten a miss. The table states it per row.

### D4. Rejected ideas

Rows that cite the ExFAT floor ("Reading part of each decode miss from the external TB5 copy") get the APFS figure added; a row is removed only by the change that later keeps the idea.

## Risks / Trade-offs

- Thermal drift between the ExFAT and APFS sessions -> each harness run is an A/B inside one session; only the probe compares across sessions, and it reads both drives in the same run.
- The APFS volume is 37% full, the ExFAT one was 93% full -> noted with the figures; free space alone can change write speed, not cold reads.
- The drive must stay connected through the session -> the user is told before it starts.

## Migration Plan

Branch `sf/250-external-apfs-evidence` from `main`; documentation and perf-record only. No commit or push without a request.
