# Design

## Context

See proposal.md. Engram tables are about 188.83 GiB but each text token requests only 48 rows of 264 bytes. `ds41_graph_alloc` currently verifies the table file and canonical GGUF share an inode. `70` may hide decode reads, and `120` may reduce exposed work further. The external device's sustained small-read rate is lower; iobench's equal short-batch times include thread startup and use different alignment from Engram.

## Goals / Non-Goals

**Goals:** test whether isolating random reads from bulk internal traffic improves actual request time, with an explicit exact source.

**Non-Goals:** freeing internal space while retaining the full original GGUF, splitting/repacking model files, changing token hashes/row values, or declaring a capacity-only feature a performance win.

## Decisions

### D1. Independence and start gate

Execute after the `140` decision, but it need not have landed. Start from `120`'s measured exposed Engram cost (its task 1.2, re-read on the post-`120` tree) rather than a new survey; add only the readiness under concurrent expert IO that `120` does not isolate. No exposed Engram time closes both the isolation and the split placement. Compare isolated storage first with dual-SSD up delivery disabled. No exposed contention means a closed gate and no runtime change. A raw-device latency parity result alone does not open it.

### D2. Explicit source

Read `DS4_ENGRAM_REPLICA` once at engine open. Unset/empty preserves the canonical same-inode behavior. A nonempty request is supported only for single-box Metal SSD streaming and must fail clearly in unsupported modes. Accept an existing complete GGUF replica; check architecture, table names, row counts, E4M3/E8M0 storage, offsets, hash multipliers/primes/token map and all externally used range bounds. Reject the canonical inode as a redundant request.

Replace the same-inode check only after comparing both Engram tables byte-for-byte with the canonical file, using bounded 1 MiB buffers, stable open descriptors and before/after file-stat checks. Reuse `140`'s landed engine-owned range validator if available, otherwise implement only the narrow helper needed here. Preserve `ds4_engram_table_open`'s range and uncached-fd validation. Never treat matching metadata as matching content.

Validation happens once per engine, not per session, and is logged separately. Hold validated source handles and duplicate/open session descriptors against that admitted identity; a later pathname replacement must not switch data silently. Reset any `120` row-cache generation when reopening. Model files are immutable during a run; observed mutation invalidates admission.

### D3. Keep the reader and semantics

The existing bounded row reader, conversion, sorting, deduplication, image masking and asynchronous producer remain unchanged except for the admitted fd/offset source. There is no extra reader pool and no whole-table mmap or RAM allocation. A split placement assigns a fixed number of the existing readers to the admitted replica and the rest to the canonical fd; rows, sorting and deduplication are unchanged, only the fd a reader uses differs. Read errors, invalid values and early EOF follow the existing error contract; engine/session teardown joins work before releasing tables. Do not create an unbounded retry or silently substitute a different file after a failure.

### D4. Evaluate placements separately

Measure (A) canonical-only, (B) external Engram with internal experts, (D) Engram split across both devices, and, only if `140` is kept, (C) external up plus Engram against the best accepted placement. B and D are one mechanism: during measurement a diagnostic `DS4_ENGRAM_REPLICA_SHARE` sets the replica's share of readers (all of them is B; the 139k/173k row-IOPS ratio suggests about 45% for D, to be measured, not assumed). The kept placement becomes the fixed behavior of `DS4_ENGRAM_REPLICA` and the diagnostic is removed; no permanent choice between equivalent placements. Small random IO may reduce external bulk throughput, so C is not assumed superior. A losing combination is documented and not promoted as the recommended setup.

Use actual `ds4_engram_read_batch` addresses/workers and conversion when diagnosing latency. Synthetic fixtures cover the same metadata with wrong contents, mismatched token maps, mutation/reopen, EOF, image masks and cancellation. Whole-model bitwise comparisons include session save/restore and prompt continuation, not merely a 24-read microbatch.

Target normal `cold,append`; timed decode and long guards protect `70`'s overlap. Keep the same expert slots and allocation budget. Judge exposed TTFT/decode under the project keep rule; no neutral additive feature survives for a potential storage-space benefit. Report engine-open scan time, fresh-process TTFT and repeated-request break-even, since validating 188.83 GiB may erase a short-lived benefit. Small kind groups must fit the existing harness budget; inability to measure within it is a stop for a separate measurement-plan revision, not permission to omit verification.

Use existing `--b-env` for ablations. For a final record row, shared explicit `--env DS4_ENGRAM_REPLICA=...` is valid only if source inspection and activation logs prove A ignores the new option and B consumes it; record the topology with the row. Otherwise keep diagnostic labeling and resolve evidence format before closure. Verify the parity oracle tests the actual candidate, with the secondary source both enabled and absent.

### D5. Deferred capacity alternative

A compact Engram file alone does not shrink the canonical internal GGUF. Actual space recovery would need a supported split-main layout or another explicit storage-format design. Do not punch holes in, truncate or rewrite the shared HF blob. That alternative requires a new capacity-focused proposal and explicit data-operation approval, rather than adding a packer to this change.

## Risks / Trade-offs

- External row latency is worse -> require the contention benefit to outweigh it in real requests.
- Full verification is expensive: both tables are 188.83 GiB, about 30 s per engine open at the external 6.38 GB/s -> report startup and amortization, no hidden persistent trust cache. Acceptable for a long-lived server; a one-shot CLI run likely pays more than it gains.
- Different inode loses page-cache locality or hides wrong data -> bounded content validation and stable descriptor identity.
- Combined placement saturates external IO -> independently measure B and C; do not sum their estimated gains.

## Migration Plan

Use `perf/150-engram-storage-isolation` only after predecessors are resolved. The option is off by default; removing it returns to the existing single-file path. No disk setup or copy occurs automatically, and no filesystem, firmware or global environment changes are made. A closed speed gate leaves only recorded evidence, not a new runtime surface. Commit/push requires a separate request.
