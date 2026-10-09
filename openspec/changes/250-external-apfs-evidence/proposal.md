# Proposal

## Why

The external TB5 drive was reformatted from ExFAT to APFS on 2026-10-08 (volume `ExtSSD`, the `140` copy at `/Volumes/ExtSSD/sf-ds4-1flash/DeepSeek-V4.1-Flash-Q2.gguf`). On this macOS, ExFAT is not a kernel file system: it runs as an FSKit extension in user space (`/System/Library/ExtensionKit/Extensions/com.apple.fskit.exfat.appex`). APFS runs in the kernel. Every figure the child holds about the copy was measured through that user-space path, and three of them have no traced cause:

- `145`: the copy's floor of about 0.6-0.7 ms for a 2.2-2.9 MiB read in 4 pieces, against 0.33 ms for a whole 9.49 MiB expert on the internal drive. That floor is why splitting decode misses across the drives measured -1.7%.
- `180`: with the copy admitted, steady decode after an 8192 context was 1.9% lower and decode miss preads averaged 0.76 ms against 0.73 ms, although decode never reads the copy.
- `190`: in upstream ds4, the routed `up` stage ran about 2x slower when bound from the copy's mmap mapping.

A per-I/O hop through a user-space file system explains all three. Before any change that uses the copy differently, the figures have to be measured again on APFS.

## What Changes

Measurement only, no runtime code. The external drive must be connected.

- **Copy latency.** The `145` probe again: random experts read the way decode reads them (4 pieces aligned to 16 KiB per family, concurrent, `F_NOCACHE` on both files), k/4 of up's pieces from the copy, k = 0..4, with 1, 2 and 3 missing experts per layer. The probe is rebuilt in the scratchpad.
- **Prefill with the copy (`140`).** Harness `cold,append` with and without `DS4_METAL_PREFILL_REPLICA`, `--bitwise`.
- **Decode with the copy admitted (`180`).** Harness `decode` with and without the copy admitted, plus the first token after an 8192 context and the miss pread time from the streaming summary.
- **KV cache on the drive (`160`).** The server diagnostic of `160` with `--kv-disk-dir` on the internal SSD and on `ExtSSD`, now that APFS journals and `F_FULLFSYNC` is real.
- **mmap from the copy.** A standalone Metal probe binding the copy's mapping as the `190` approach did, against the model's mapping. It decides whether the deferred-decoder sweeps (prompts from about 24.5K) could read `up` from the copy; that is recorded as a note and is not a proposal of its own.
- `speed-bench/perf-record.md` gets a section with the ExFAT and APFS figures side by side. `docs/ssd.md`, `docs/MacM5.md` and the README's second-drive section say APFS. Rows in Rejected ideas whose reason no longer holds are reworded.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `speed-bench/perf-record.md`, `docs/ssd.md`, `docs/MacM5.md`, `README.md` (second-drive section and its speed table).
- Decides whether `260-dual-drive-split-retune` goes ahead and with which split points.
- No runtime code; the probes live in the scratchpad.
