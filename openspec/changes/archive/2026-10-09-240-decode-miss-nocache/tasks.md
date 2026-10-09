# Tasks

## 1. Gate: page-cache share of today's misses

- [x] 1.1 Read the miss-source table of `225-mac-memory-evidence` (share of decode misses served under the drive latency) and its file-backed pages during decode: the ceiling of the loss and the memory returned (D4). Verify `225` is complete; if the share is near zero and the file-backed pages are small, record that the change closes. (Read: `225` is complete. The file cache serves 20% of the `decode` miss reads and 28% of the `append` ones at about half the drive's time, so uncached reads would cost about 0.8% decode and more on appends; file-backed pages are 23-25 GiB, but the memory returned pays only if it becomes cache slots, and the lever that would use it, `230` S1, was dropped. The change closes here; recorded in `perf-record.md` Rejected ideas.)

## 2. Uncached decode misses

- [x] 2.1 (Not run: the gate closed in 1.1.) Open the uncached descriptor at `ds4_gpu_set_model_fd` (same device, inode and size; `F_NOCACHE`, `F_RDAHEAD 0`), close it at cleanup; the pool chooses it per load behind `DS4_METAL_V41_DECODE_MISS_NOCACHE=1`, skips the `F_RDADVISE` warm-up in that mode, and falls back to the cached descriptor for a failed piece, counted in the streaming summary. Verify `make test`, `test-metal-ssd-experts`, and `make test-deepseek41-decode-switch SWITCH=DS4_METAL_V41_DECODE_MISS_NOCACHE` bitwise.
- [x] 2.2 (Not run: the gate closed in 1.1.) Harness A/B `decode,append` with `guard-16896,guard-decode`, `--bitwise`, B with the switch on, `vm_stat` pageouts and pageins sampled once a second. Verify the keep rule; record the row with the pageout figures and the first token after the sweep. If kept, flip the default and rename the switch to `DS4_METAL_DISABLE_V41_DECODE_MISS_NOCACHE`, rerunning the decode-switch test; if not, remove the code and add the row to Rejected ideas.

## 3. Integration

- [x] 3.1 (Not run: the gate closed in 1.1.) Review against `AGENT.md`; the switch in `AGENTS.md`; `make`, `make cpu`, `make test`, the model-backed checks and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`; `openspec validate 240-decode-miss-nocache --strict`. No commit or push without a request.
