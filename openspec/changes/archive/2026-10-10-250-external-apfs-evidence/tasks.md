# Tasks

## 1. Copy latency

- [x] 1.1 Rebuild the `145` latency probe in the scratchpad (D2) and run it against `/Volumes/ExtSSD/sf-ds4-1flash/DeepSeek-V4.1-Flash-Q2.gguf` and the model, with the gate/down extension. Verify the 0/4 column reproduces the internal drive's ExFAT-era figure within 10%, then record the table in `speed-bench/perf-record.md` with the D3 verdict per row. (Done 2026-10-09. The 0/4 check fails: 0.971 ms against 0.772. The `145` figure included page-cache hits: its p10 of 0.335 ms is 29.7 GB/s, twice the drive. This run reads at drive speed; explained in the section.)

## 2. Harness on APFS

- [x] 2.1 Harness `cold,append` with and without `DS4_METAL_PREFILL_REPLICA`, `--bitwise`, same budget as `140`. Verify the run is bitwise and record the row beside the ExFAT one. (Done 2026-10-09: two invocations, 65 pairs, bitwise, timed rounds at Heavy. The sweep shapes gain as on ExFAT.)
- [x] 2.2 Harness `decode` with and without the copy admitted, plus the first token after 8192 and the miss `pread` time from the streaming summary. Verify bitwise; record whether the `180` -1.9% remains. (Done: decode 8192 -0.56%, CI below zero. Misses read 0.08 ms slower with the copy admitted. The first token after 8192 gains 1.24 -> 0.88 s, against 1.38 -> 0.18 s on ExFAT; cause open.)

## 3. KV and mmap

- [x] 3.1 The `160` server diagnostic with `--kv-disk-dir` on the internal SSD and on `/Volumes/ExtSSD/sf-ds4-1flash/kv-bench250`, cold and hit shapes, ABBA. Verify both arms complete with the same tokens; record store and load times. (Done: on APFS a store takes 16.0 ms against 22.5 internal, a load 13.6 against 9.8; placement stands.)
- [x] 3.2 Standalone Metal probe: bind `up` of one layer from the copy's mapping and from the model's, `pread`-warmed and cold, timing a routed `up` dispatch. Record whether the `190` 2x remains; write the deferred-decoder note. (Done 2026-10-09 with a read kernel, not the routed `up` kernel. Warm: equal. Cold: drive speed, 5.5 against 10.5 GB/s. The in-engine 2x of `190` cannot be reproduced standalone and needs the `190` port's stage profile on APFS. Note written.)

## 4. Documentation

- [x] 4.1 Update `docs/ssd.md`, `docs/MacM5.md` and the README's second-drive section (APFS, the new path, the APFS figures); add the APFS figures to the Rejected ideas rows that cite the ExFAT floor; `openspec validate 250-external-apfs-evidence --strict`. No commit or push without a request.
