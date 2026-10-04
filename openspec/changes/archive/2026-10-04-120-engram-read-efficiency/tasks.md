# Tasks

## 1. Exposed Engram cost

- [x] 1.1 After `110`, prepare `perf/120-engram-read-efficiency` and the baseline; verify `70`'s effective async path and named `make test-engram`/graph results before attributing failures. (Branch at `631fdda`; `make test-engram` and the named `make test` suite green; `70`'s decode reads join at layers 1 and 14.)
- [x] 1.2 Measure actual read, conversion, sorting, reuse and readiness costs plus prefetch allocation on cold/append/decode shapes. Verify the performance record names which independent gates open; no iobench batch-startup number substitutes for runtime evidence. (Timers in the real reader and around the decode joins on cold-2500, cold-7500, append and decode; record section "Engram reads after 110". Every gate closed: conversion under 1 us of a 0.66 ms row, duplicates 4-8% already deduped per partition, prefetch output memory-only, decode wait 0.02-0.05 ms per token.)

## 2. Exact conversion

- [x] 2.1 Implement D2's smallest exact conversion replacement inside the common reader. Verify all 65536 code/scale combinations against the original implementation, including errno, signed zero, subnormal/overflow behavior, and unchanged non-fast-math compilation. (Closed at the D1 gate: conversion is under 0.5% of the readers' time, a few ms per sweep. Not implemented.)
- [x] 2.2 Review and measure conversion alone with bitwise harness runs; record the decision and conversion rationale next to the code. Verify additive neutral code is removed before later trials. (Not run: 2.1 closed; nothing to measure or remove.)

## 3. Deduplication and optional row cache

- [x] 3.1 Partition duplicate runs safely and scatter back to original positions; add cross-partition duplicate and error cases. Verify `make test-engram`, named graph tests and an independent normal-harness keep verdict; document the ownership rule and result. (Closed at the gate: a cross-partition repeat can only fall on the 15 boundaries of a 2048-token batch, against 4-8% duplicates already deduped. Not implemented.)
- [x] 3.2 Only if cross-batch reuse warrants it, add D3's bounded cache with generation checks and 0/1/4 MiB diagnostic comparisons. Verify full key equality, same-inode rewrite/truncate, reopen/reset, invalid-row and worker-error tests; keep expert slots unchanged. (Closed: cross-batch reuse is bounded by the same few percent of a 0.2-0.8 s wait per sweep. Not implemented.)
- [x] 3.3 Review and measure the cache independently across fresh/warm sessions, retaining at most one measured default. Verify its budget includes tags, mutation errors are not hidden, and the performance record contains its keep/drop evidence. (Not run: no cache was added.)

## 4. Optional prefetch ring

- [x] 4.1 If the allocation gate opens, implement two consumer-sized tiles without changing numerical chunks. Add ring wrap, slow consumer, layer/table transition and cancellation tests; verify the producer never overwrites data before its GPU copy completes. (Gate closed: the 768 MiB output sits in the static context and freeing it cannot change speed with the expert cache held fixed. Not implemented.)
- [x] 4.2 Measure normal TTFT/decode and memory admission against the previous kept tree. Verify no larger expert cache or changed scheduling accounts for a gain; document lifetime and result, dropping an additive memory-only neutral rewrite. (Not run: 4.1 closed.)

## 5. Integration

- [x] 5.1 Review all retained reader/lifetime paths; build Metal and separate CPU targets, run named tests and model-backed image-mask/session save/restore/eval checks. Verify exact bytes and error semantics with and without each kept diagnostic ablation. (No runtime code remains: `ds4.c`, `ds4_engram.c`, `ds4_metal.m`, `metal/` and the tests equal `main`. `make` and `make cpu` without warnings, `make test` and `make test-engram` green; model-backed checks have nothing new to check.)
- [x] 5.2 Complete segment-start A/B and actual-candidate upstream parity under SSD streaming, append the row and update only relevant PR verdicts. Verify `openspec validate 120-engram-read-efficiency --strict`, closed-stage dispositions and final scope; do not commit/push without another request. (No runtime change, so no segment row and no parity run, as for `80`, `90` and `110`; record and rejected-idea rows updated; no upstream PR was acted on.)
