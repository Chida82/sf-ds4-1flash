# Design

## Context

See proposal.md. `ds4_engram_read_batch` sorts bounded batches, deduplicates within each reader partition and uses 16 GCD workers. `ds4_engram_read` converts bytes with ldexpf and rounds to BF16 stored as F32. `tests/test_engram.c` already exhausts 256 codes x 256 scales, including invalid values and signed zero, and tests file mutation/truncation. The full-prefix prefetch allocation can reach 768 MiB; decode overlap may already be addressed by `70`.

## Goals / Non-Goals

**Goals:** reduce exposed conversion/readiness overhead and unnecessary temporary storage with exact row values.

**Non-Goals:** new hashing, approximate memory, different image masking, an ANE/SME backend, changed numerical chunks, or external Engram placement.

## Decisions

### D1. Gate each cost independently

Start after `110` is resolved. Separate uncached reads, conversion, sorting, duplicate rows and time actually waiting for Engram after `70`. Reuse the real read path for probes; the storage benchmark's thread-create/16-KiB-aligned batches are not its latency oracle. Conversion, dedup, row caching and prefetch storage are separate trials; close any whose measured ceiling is below the decision resolution.

### D2. Exact conversion first

Prefer a 256-entry code-value table plus the existing scale/round logic, then bit construction or NEON only if the remaining conversion cost warrants it. Preserve invalid E4M3 codes, scale 255 rejection, overflow, subnormals and negative zero. Compare every code/scale against the original scalar result and errno, not against an approximate mathematical value. Keep ds4_engram.c's existing exclusion from fast-math. This is a replacement inside the common reader, so every caller benefits without per-caller conversions.

### D3. Deduplication and bounded row cache

Partition sorted requests at equal-row run boundaries so one unique row is read/converted once per batch, then scatter to the original output positions. Keep work disjoint and error collection deterministic; no new thread pool.

Only if cross-batch reuse is meaningful, trial a table-owned fixed-size raw-row cache with a combined budget of at most 4 MiB including tags for the two tables. Compare 0/1/4 MiB in diagnostics, then retain at most one measured default, not a tuning surface. Full key equality is required; collisions cause misses. Prepare cache hits/misses on the coordinating thread and publish worker results after join, avoiding a shared hot lock.

Bind cache validity to the open table/file generation; clear it on close, reopen or observable size/mtime/ctime change before a batch. Do not change the uncached public reader's mutation/error behavior. Tests rewrite and truncate the same inode after filling the cache. If the checks or memory compete away the speedup, omit the cache entirely. Concurrent modification during an active inference remains unsupported, as for canonical weights.

### D4. Prefetch output lifetime, separate trial

Only if the allocation is material, replace prefix-sized decoded output with a two-tile ring sized from the unchanged consumer tile sizes. The producer cannot overwrite a tile until the consuming GPU copy completes; layer-1 and layer-14 generations remain distinct. Keep the current prefetch path for flows not covered by the proof. Cancellation wakes/joins the producer, settles copies and invalidates partial session state. Saved memory does not increase expert slots in the A/B, and must not change admission enough to change the prefill schedule.

A memory-only additive rewrite is not a speed win: if it does not satisfy the project's gate, revert it. Do not require it for later storage isolation.

### D5. Tests and evidence

Use the existing exhaustive oracle and add cross-partition duplicates, invalid rows before output writes, warm-cache mutation/EOF and close/reopen cases. Extend graph prefetch tests for ring wrap, backpressure, table transition and cancellation only if D4 proceeds. `make test-engram` and the named `make test` suite run after each stage; no extra numerical framework.

Targets: `cold,append`, plus timed decode if decode exposed time was the gate; guards: both long kinds, image-mask regression and session restore. Use normal harness timing because CPU/GPU overlap changes, with bitwise logits/state. A raw-row cache is not an expert-cache-policy change: keep expert drift checks. Finish under the project per-step keep rule, full-region review, segment-start row and candidate-verified upstream parity.

## Risks / Trade-offs

- Compiler changes edge-case rounding -> exhaustive original-path comparison.
- Cache hides corrupt/truncated data -> generation checks and existing mutation oracle remain binding.
- Smaller prefetch buffer loses overlap -> compare readiness stalls and normal TTFT; do not keep on memory size alone.
- Layer/table races -> bounded ownership, cancellation fixtures and no background accesses after close.

## Migration Plan

Use `perf/120-engram-read-efficiency`. No persistent data conversion or public option. One release path with tested fallback; delete losing variants. Registry changes only for actually adopted/rejected upstream work. No commit or push without a later request.
