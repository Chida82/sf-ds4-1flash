# Proposal

## Why

`130`'s profile of streaming decode (2048 and 8192, 256 tokens) shows the GPU idle about 12 ms of a 41 ms token. Each of the 40 layers waits for its selected expert ids: about 295 us pass between the router command buffer ending on the GPU and the expert command buffer starting, and 76 us of that is the CPU waking up from `waitUntilCompleted`. A short, bounded poll can wake within microseconds; at 40 waits per token that is up to about 3 ms, about 7% of decode.

## What Changes

- At the selected-id readback of streaming decode, poll the completion for a bounded time before falling back to the existing blocking wait. The fallback, timeout, error and cancellation paths stay as they are.
- Reuse the existing shared-event helper (`ds4_gpu_signal_batch_and_wait_event`, today used only by the Q4 selected path) or the command buffer's status, whichever the measurement shows wakes faster; no new thread, queue or event object per call.
- The poll bound is a measured constant, not a tuning surface. No change to what is encoded, to the flush schedule kept by `30`, or to cache ownership.

## Capabilities

### New Capabilities
None. Host-side wait only (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: the readback boundary in `ds4_gpu_routed_moe_one_tensor` and one wait helper.
- Tests: the existing command-memory, streaming-cache and graph queue tests; `make test-deepseek41-decode-switch` with the rollback switch.
- Costs a CPU core spinning up to the bound per layer: measured as power-neutral enough only if the decode gain is real; the bound keeps a stalled GPU from turning into an unbounded spin.
- No external SSD.
