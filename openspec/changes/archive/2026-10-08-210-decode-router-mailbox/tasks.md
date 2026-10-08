# Tasks

## 1. Gate

- [x] 1.1 Prepare `perf/210-decode-router-mailbox` from `main` and the worktree of the segment's start commit. Re-run `132`'s flag probe timing the CPU's sight of a one-thread kernel's store against that kernel's `GPUEndTime` (400 iterations, median and p90); on the same run check whether the batch's compute encoder orders dispatches serially on the decode path. Verify the performance record states both; close the change if the median is above 35 us.

## 2. Mailbox

- [x] 2.1 Add `kernel_dsv41_selected_publish`, the shared box and the poll; encode the publish as the router batch's last dispatch inside `ds4_gpu_split_readback` (the `132` split stays, D1), behind `DS4_METAL_DISABLE_V41_READBACK_MAILBOX`. Verify `make` and that a decode run prints hits and no fallback beyond the post-prefill one (D5).
- [x] 2.2 At the readback (`ds4_gpu_commit_split_wait_pending`), commit the shared-expert batch, poll the mailbox, skip the tensor read on a hit, fall back to the waited path on a timeout with a counter in the streaming summary. Verify `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_READBACK_MAILBOX` passes bitwise.
- [x] 2.3 On a hit, wait only the buffers committed before the router batch and move the cache's done sequence to just below it (D4). Verify the streaming-cache, decode-queue and command-memory tests pass and the hit rates equal the `132` path in the harness.
- [x] 2.4 A/B `decode,append` with the long and cold guards, `--bitwise`, against the previous kept tree; record the row, the per-layer components after and the fallback count. Verify the keep rule; remove the code if not kept. If kept and the harness can still resolve it, try folding the publish into the router kernel as a refinement measured the same way.

## 3. Integration

- [x] 3.1 Review the touched region against `AGENT.md` and the surrounding idiom; add the switch to `AGENTS.md`'s list and the Argodrive provenance line to `docs/upstream-prs.md`; build `make` and `make cpu`, run the named `make test` suite and the model-backed session checks (`ds4_test --all` with streaming: ok) and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`. Verify `openspec validate 210-decode-router-mailbox --strict`. No commit or push without a request. The segment-start A/B ran on 2026-10-08 with the machine in use and was inconclusive (4 of 20 pairs, GPU median 941 MHz); by owner decision it moves to one measurement after the next proposals, against the README figures.
