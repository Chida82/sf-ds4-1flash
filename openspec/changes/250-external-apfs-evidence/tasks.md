# Tasks

## 1. Copy latency

- [ ] 1.1 Rebuild the `145` latency probe in the scratchpad (D2) and run it against `/Volumes/ExtSSD/sf-ds4-1flash/DeepSeek-V4.1-Flash-Q2.gguf` and the model, with the gate/down extension. Verify the 0/4 column reproduces the internal drive's ExFAT-era figure within 10%, then record the table in `speed-bench/perf-record.md` with the D3 verdict per row.

## 2. Harness on APFS

- [ ] 2.1 Harness `cold,append` with and without `DS4_METAL_PREFILL_REPLICA`, `--bitwise`, same budget as `140`. Verify the run is bitwise and record the row beside the ExFAT one.
- [ ] 2.2 Harness `decode` with and without the copy admitted, plus the first token after 8192 and the miss `pread` time from the streaming summary. Verify bitwise; record whether the `180` -1.9% remains.

## 3. KV and mmap

- [ ] 3.1 The `160` server diagnostic with `--kv-disk-dir` on the internal SSD and on `/Volumes/ExtSSD/sf-ds4-1flash/kv-bench250`, cold and hit shapes, ABBA. Verify both arms complete with the same tokens; record store and load times.
- [ ] 3.2 Standalone Metal probe: bind `up` of one layer from the copy's mapping and from the model's, `pread`-warmed and cold, timing a routed `up` dispatch. Record whether the `190` 2x remains; write the deferred-decoder note.

## 4. Documentation

- [ ] 4.1 Update `docs/ssd.md`, `docs/MacM5.md` and the README's second-drive section (APFS, the new path, the APFS figures); add the APFS figures to the Rejected ideas rows that cite the ExFAT floor; `openspec validate 250-external-apfs-evidence --strict`. No commit or push without a request.
