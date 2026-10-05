# Proposal

## Why

The internal SSD and ACASIS TB501 Pro / Samsung 9100 PRO pair sustained about 13.0 + 6.38 GB/s together in the recorded bulk-read tests. After `130`, use the slower external device to contribute roughly one third of prefill reads, rather than replace the internal drive or assume a 50/50 stripe helps.

## What Changes

- Add opt-in `DS4_METAL_PREFILL_REPLICA=<existing-GGUF>` for single-box Q2 SSD prefill: read routed `up` weights from a validated replica, `gate/down` from the canonical internal GGUF, and resident cache hits from RAM first.
- Keep the two disk groups genuinely concurrent while filling the same two-layer Metal buffers. Preserve kernels, numerical partitions, cache capacity and decode's internal-file path.
- Validate the selected replica ranges byte-for-byte with bounded memory before their use, report validation/startup cost, and fail safely on invalid input or I/O errors.
- Use a complete existing GGUF replica for the first implementation. A 43.51 GiB up-only derivative, weighted chunk scheduling and dynamic decode striping remain alternatives, not mandatory work.
- No automatic copying or cache relocation. An implementation run needs a user-supplied validated source or separate explicit approval of any large external-file creation.

## Capabilities

### New Capabilities
- `dual-ssd-prefill`: opt-in validated secondary source for routed-up prefill bytes, safe concurrent delivery and unchanged default operation.

### Modified Capabilities
None. Existing explicit harness environment settings and evidence are sufficient; no generic storage-profile framework.

## Impact

- `ds4.c` replica admission and explicit-reader scheduling; minimal Metal helper changes only if the kept `100` reader uses Metal I/O.
- Graph/loader/error-path tests, streaming docs, performance record and storage-topology evidence. The engine-level environment option applies consistently across frontends; no new download mode.
- Requires a passing explicit-buffer path from `60`; wide coverage requires the kept wide-buffer work from `100`. If that step was dropped, evaluate only the supported shapes, without resurrecting it as scaffolding.
- A 30.56% external byte share implies approximately 18.72 GB/s / 1.44x transfer throughput under ideal bulk conditions, not a measured TTFT or decode gain.
