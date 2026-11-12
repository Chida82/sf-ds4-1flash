# Proposal

## Why

Every System One figure here is measured on one 128 GB Mac under SSD
streaming. `docs/system-one.md` section 10 records what more machines would
change according to the code: two Macs in tensor parallel hold the main
weights resident (no streaming), and session batching, which
`ds41_sessions_batch_supported` refuses under streaming, becomes available.
Nobody has measured how much of a decision's time that would remove. Without
that number, "would more machines help a lot?" cannot be answered, and a
second machine cannot be justified or ruled out.

Part of the answer is measurable today, on one Mac: split a decision's wall
time into GPU compute and waiting for SSD reads. The compute share is the
floor a resident machine could reach; the read share is the most residency
can remove.

## What Changes

- Stage 1 (one Mac, no purchase): a timed decomposition of the `820`
  decisions into GPU time, read wait and the rest, for short states (token by
  token) and swept states, written as a "residency headroom" table.
- Stage 2 (dropped 2026-11-12, no second Mac; estimated from stage 1 in the
  record instead; originally, only when a second Mac is cabled): the same bench against a
  tensor-parallel server, the measured speed-up against stage 1's prediction,
  and a session-batching check for question branches.
- A go/stop rule after stage 1 that says whether stage 2, and any batch
  design (`a045`, micro-batching), is worth pursuing.

## Non-goals

- No engine edit. Stage 1 uses existing probe variables only.
- No purchase recommendation beyond the measured ratio.
- Pipeline (layer-slice) parallelism: it does not work for V4.1 yet.

## Impact

- `sysone-bench/headroom.py` (log parser), `sysone-bench/record.md`.
- `docs/system-one.md` section 10 gains the measured table.
