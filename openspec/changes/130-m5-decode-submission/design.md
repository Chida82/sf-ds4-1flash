# Design

## Context

See proposal.md. `ds4_gpu_get_pipeline` constructs NSString keys; specialized fast lookups and hot pipeline pointers already exist. The runtime creates `newCommandQueueWithMaxCommandBufferCount`, despite detecting MTL4 availability. Streaming MoE reads selected IDs on the CPU, and even the existing GPU hit validator ends commands before reading its result. These are real dependencies, not missing feature toggles.

## Goals / Non-Goals

**Goals:** remove measured host overhead without changing GPU arithmetic or cache ownership.

**Non-Goals:** porting the whole runtime to MTL4, GPU miss servicing, CPU/GPU polling without a bound, moving matvecs to SME, or replacing the `70` fusions with a competing PR.

## Decisions

### D1. Profile the accepted graph, not the old wait counter

After `120`, attribute CPU encode/allocation work, GPU kernel time and gaps with the existing timeline and installed system tools. Probe timings are not throughput verdicts. Use warm decode 2048/8192, a first token after prefill, append +300 and the long answer. Implement only when a bounded candidate can exceed the A/A resolution; GPU work inside `sync` is excluded from the recoverable-overhead estimate.

### D2. Existing lookup mechanism

Review #1067 `d1738d2` against the current getters. Extend existing fast-key/cache logic or use a retained hot pipeline pointer for fixed names, preserving function constants, negative-cache entries, initialization and cleanup. No second hash table if an existing one serves the same key. Compile/create pipelines on the existing safe owner thread; do not revive the keep-alive pipeline race discussed in #1126. Tests compare selected pipeline/constant identities and behavior across reset and disabled diagnostics.

### D3. Narrow command coalescing

Only if encoding transitions remain visible after D2, retain the current command queue and coalesce adjacent safe compute groups. Preserve blit dependencies, resource hazards, streamed readback, event generation, buffer reuse and public cancellation boundaries. Limit the trial to the measured single-box decode region; TP and layer-slice entry points retain their established behavior. Do not redo `30`'s rejected two-layer flush schedule. Failure to identify a safe local region closes this step.

### D4. Expensive alternatives are explicitly deferred

- MTL4 allocator/argument-table submission: requires explicit hazards and lifetimes across many wrappers. Reusing a buffer object is not graph replay. Reconsider only if remaining measured host gaps justify a separate bounded migration design.
- GPU all-hit continuation: needs valid-slot protection, miss reporting, bounded stop/resume and no partial KV publication. The current validator still synchronizes. Do not implement a speculative scheduler in this change; a future proposal must define the recovery state machine first.
- ANE/SME partitioning: adds a backend/rounding/synchronization problem, not a submission optimization.

Capturing these alternatives is not an unfulfilled implementation task: the selected approach deliberately stops at D2/D3.

### D5. Proof and acceptance

Run existing pipeline-cache test hooks, `make test-metal-command-memory`, slab/cache tests and same-engine graph queue parity. Stress first-use compilation, reset/reopen, delayed completion, error exit and cancellation; outputs and session state are bitwise with the previous path. Re-run model-less tests on the baseline worktree to identify pre-existing failures.

Each step uses normal `decode,append` A/B, with cold and long guards, not stage-time substitution. Respect the per-step CI/size gate; an additive neutral fast path is dropped. End with the segment-start row, affected PR verdicts and parity verified to target the candidate. If substantial unexplained GPU gaps remain, record the evidence for a follow-up rather than expanding implementation scope.

## Risks / Trade-offs

- Incomplete pipeline keys select the wrong specialization -> constants/shape identity tests.
- Coalescing extends a buffer lifetime or hides an error -> completion/cancel fixtures and unchanged readback boundaries.
- `70` already removed most lookup overhead -> accept a no-op result.

## Migration Plan

Branch `perf/130-m5-decode-submission`; no user API, persistent state or required OS upgrade. Use diagnostic ablations during measurement, keep one accepted path, and review all touched regions for dead code. Commit/push and distributed hardware runs need separate requests.
