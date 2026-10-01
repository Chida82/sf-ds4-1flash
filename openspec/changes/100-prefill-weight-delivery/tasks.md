# Tasks

## 1. Delivery baseline

- [ ] 1.1 Resolve earlier changes and verify `60`'s explicit buffers are present before creating `perf/100-prefill-weight-delivery` and its baseline. Run the baseline graph/model-less suite and confirm the 7.12 GiB reserve and identical admitted expert slots; stop for replanning if the prerequisite was rejected.
- [ ] 1.2 Attribute exposed ready/map waits versus overlapped reads, GPU work and seeding for D1's shapes. Verify the performance record states each stage's recoverable cost; do not retain delivery scaffolding solely for `140`.

## 2. Wide-buffer lifetime

- [ ] 2.1 Extend ordinary wide-sweep buffer lifetime through preparation, all tiles and seeding, leaving numerical scheduling and unproven encoder-only/resume flows unchanged. Add graph fixtures for multi-tile reuse, suffix preparation and cancellation; verify raw layer bytes, join/drain order and rejection of partial session snapshots.
- [ ] 2.2 Run named graph/Metal tests, review and A/B `cold,append` with timed decode and long guards. Verify bitwise state/logits and fixed slots, document supported flows and keep/drop evidence, and remove an additive neutral extension.

## 3. Reuse resident expert bytes

- [ ] 3.1 Add a non-touching ready-entry lookup/copy path and temporary source protection, plus coalesced missing ranges. Verify tests cover in-flight sources, delayed blits, seeding/eviction pressure, exact byte coverage and unchanged victim/counter semantics; disk workers must not access cache metadata.
- [ ] 3.2 Review and measure against the previous kept state; record RAM-copy bytes, disk-request bytes and exposed wait separately. Verify normal harness throughput and cache-state checks pass; drop byte-saving code that does not improve the measured target.

## 4. Optional native I/O trial

- [ ] 4.1 If a host/readiness cost remains, implement D4's narrow Metal-I/O trial on the same ranges and buffers. Add deterministic completion/error/cancel tests; verify availability fallback, status checks and no reuse/free until IO and GPU consumers settle.
- [ ] 4.2 Compare to the pread route with unchanged memory admission and normal harness timing. Verify an independent keep verdict, document the supported route and failure semantics, and delete native-IO trial code if it is neutral or slower.

## 5. Integration

- [ ] 5.1 Review all retained lifetime paths and run `make`, `make cpu`, the named `make test` suite, `make test-metal-ssd-experts`, Metal model tests and session/eval checks with SSD streaming. Verify no third buffer, new quantization or changed prompt partitions entered the final diff.
- [ ] 5.2 Record the segment-start A/B row and actual-candidate parity; update storage docs and any acted-on #952 verdict. Verify `openspec validate 100-prefill-weight-delivery --strict`, explicit dispositions for closed stages, and unchanged unrelated files. No automatic commit/push.
