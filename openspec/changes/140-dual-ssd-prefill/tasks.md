# Tasks

## 1. Hardware and exposed-wait gate

- [ ] 1.1 Resolve changes through `130`, verify the kept explicit-buffer support, and prepare `perf/140-dual-ssd-prefill` plus its baseline. Verify named baseline graph tests and fixed cache/reserve; record whether wide/RAM-source/native-IO steps actually landed.
- [ ] 1.2 Measure internal-only layer-ready stalls and identify an existing user-approved exact replica on the external drive. Verify devices/filesystems and available source identity; if no replica exists, stop and ask before any copy. Record the gate in the performance record; stop if recoverable IO cannot meet the project threshold.

## 2. Source admission and content validation

- [ ] 2.1 Add the opt-in engine admission and bounded routed-up comparison from D1/D2. Extend synthetic GGUF/graph tests for unset/empty, unsupported modes, same inode, wrong directory, invalid bounds, identical metadata with changed payload and path replacement. Verify failure precedes inference and normal decode's fd flags remain unchanged.
- [ ] 2.2 Implement engine-owned validated-source lifetime and startup logs; test multiple sessions, early initialization failure and close/reopen. Verify verification buffers are bounded/freed before admission and sessions do not trigger rescans. Document the inline option, immutable-source requirement, off-by-default scope and startup cost in storage/help documentation as applicable.

## 3. Concurrent family reads

- [ ] 3.1 Fill the existing slot using concurrent internal gate/down and external up ranges, retaining any accepted RAM-source reuse. Add deterministic barriers in the test fixture to prove both groups start before either is joined; verify exact coverage and byte-identical completed layer buffers.
- [ ] 3.2 Exercise delayed reads, partial errors, EOF, cancel, slot reuse and unsupported-sweep fallback. Verify no layer is published before all sources complete, partial sessions remain invalid, all workers settle before free, and no external reads occur for ordinary decode.
- [ ] 3.3 Review and measure a bounded reader split at unchanged total reader budget, then A/B normal `cold,append` and guards. Verify bitwise logits/state, identical expert slots and actual source-byte/wait logs. Record the winning split/support matrix or remove the feature if the project gate fails.

## 4. Operational and final evidence

- [ ] 4.1 Measure initialization verification, fresh-process TTFT and repeated-request break-even separately from the normal inference harness. Verify every invocation remains within budget, use smaller kind groups if needed, and stop for measurement-plan revision rather than bypass verification/refusal. Update docs with measured limits, not the theoretical 1.44x IO figure as an LLM gain.
- [ ] 4.2 Review all retained source/lifetime paths, build Metal and separate CPU targets, and run named model-less/Metal/streaming session/eval tests. Verify CPU/TP unsupported requests fail, default operation remains unchanged and no data or host configuration is modified by the engine.
- [ ] 4.3 Produce the final segment-start evidence using D5's explicit environment/activation checks; append a topology-labeled row only when the harness actually emits one. Run actual-candidate upstream parity with default and enabled placement. Verify `openspec validate 140-dual-ssd-prefill --strict` and that sidecars/dynamic striping were not added. Commit/push remains separately authorized.
