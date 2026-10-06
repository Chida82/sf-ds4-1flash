# Proposal

## Why

The `145` probe showed that predicting the next layer's experts from the current router input catches about a quarter of decode misses with a top-6 window and one read per layer, and about half with a top-12 window and two per layer (`speed-bench/perf-record.md`, Decode misses after 140). `145` measured a minimal variant (layers 20-39, one read per layer) and dropped it: it caught misses as predicted, but its CPU guess (85 us per layer) and its wasted reads cost decode 1.7-2.1%. This change revisits prefetch once `150` and `160` have landed, starting from a much cheaper guess.

## What Changes

- Re-measure first. Measure the cheapest guess first, then rerun the `145` probe on the then-current `main`. Stop if the full variant's ceiling, net of wasted reads, cannot clear the harness resolution.
- Full route-prediction prefetch:
  - every layer;
  - a top-k window and a per-layer cap chosen from the probe (up to 2-3 reads per layer);
  - dedicated staging slots outside the cache budget, so a wrong guess never evicts a cached expert;
  - promotion into the cache only on actual selection;
  - eviction protection for the experts just predicted;
  - several prefetches in flight, on a reader pool separate from the demand misses.
- Optional, by measurement: prefetch reads from the `140` replica, where wasted reads cost the internal drive nothing. This needs the whole expert tables validated, about 142 GiB at engine open.
- Optional, by measurement: a learned predictor, run on the GPU, if router reuse falls short.

## Capabilities

### New Capabilities
- `decode-route-prefetch`: decode reads predicted next-layer experts ahead of their selection, with bounded staging, identical output and unchanged cache budget.

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`, the expert cache: staging slots, a prefetch reader pool, promotion and protection. `ds4.c`: the prediction and its trigger.
- Metal streaming fixtures, `speed-bench/perf-record.md`, `AGENTS.md`.
- Runs after `150` and `160`. The external SSD is needed only for the replica option.
