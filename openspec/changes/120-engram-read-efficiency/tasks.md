# Tasks

## 1. Exposed Engram cost

- [ ] 1.1 After `110`, prepare `perf/120-engram-read-efficiency` and the baseline; verify `70`'s effective async path and named `make test-engram`/graph results before attributing failures.
- [ ] 1.2 Measure actual read, conversion, sorting, reuse and readiness costs plus prefetch allocation on cold/append/decode shapes. Verify the performance record names which independent gates open; no iobench batch-startup number substitutes for runtime evidence.

## 2. Exact conversion

- [ ] 2.1 Implement D2's smallest exact conversion replacement inside the common reader. Verify all 65536 code/scale combinations against the original implementation, including errno, signed zero, subnormal/overflow behavior, and unchanged non-fast-math compilation.
- [ ] 2.2 Review and measure conversion alone with bitwise harness runs; record the decision and conversion rationale next to the code. Verify additive neutral code is removed before later trials.

## 3. Deduplication and optional row cache

- [ ] 3.1 Partition duplicate runs safely and scatter back to original positions; add cross-partition duplicate and error cases. Verify `make test-engram`, named graph tests and an independent normal-harness keep verdict; document the ownership rule and result.
- [ ] 3.2 Only if cross-batch reuse warrants it, add D3's bounded cache with generation checks and 0/1/4 MiB diagnostic comparisons. Verify full key equality, same-inode rewrite/truncate, reopen/reset, invalid-row and worker-error tests; keep expert slots unchanged.
- [ ] 3.3 Review and measure the cache independently across fresh/warm sessions, retaining at most one measured default. Verify its budget includes tags, mutation errors are not hidden, and the performance record contains its keep/drop evidence.

## 4. Optional prefetch ring

- [ ] 4.1 If the allocation gate opens, implement two consumer-sized tiles without changing numerical chunks. Add ring wrap, slow consumer, layer/table transition and cancellation tests; verify the producer never overwrites data before its GPU copy completes.
- [ ] 4.2 Measure normal TTFT/decode and memory admission against the previous kept tree. Verify no larger expert cache or changed scheduling accounts for a gain; document lifetime and result, dropping an additive memory-only neutral rewrite.

## 5. Integration

- [ ] 5.1 Review all retained reader/lifetime paths; build Metal and separate CPU targets, run named tests and model-backed image-mask/session save/restore/eval checks. Verify exact bytes and error semantics with and without each kept diagnostic ablation.
- [ ] 5.2 Complete segment-start A/B and actual-candidate upstream parity under SSD streaming, append the row and update only relevant PR verdicts. Verify `openspec validate 120-engram-read-efficiency --strict`, closed-stage dispositions and final scope; do not commit/push without another request.
