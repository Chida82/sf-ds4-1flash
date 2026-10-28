# Proposal

## Why

The steering series (`400` to `405`) touches the V4.1 graph, the engine's option handling, the prefill schedule's reconstruction and the eval harness. Each change carries its own tests, but none of them measures the whole series at once from the point of view of every user who never passes a steering option. This change is that gate, numbered with margin so later steering changes can land before it runs: the unsteered path bit for bit, parity against upstream, and the results, unsteered speed against the segment start and the steered numbers the series produced.

## What Changes

- No code. A quality pass over the tree where the last steering change landed, recorded as evidence:
  - **bits**: the model-less suite, every documented bitwise switch through `--decode-switch`, the steering state controls (no file, zero scale, zero vector, disable switch) and the route test;
  - **parity**: the oracle against upstream at the merge-base, SSD streaming, no steering options;
  - **results**: the A/B harness against the start commit of the current `perf-record.md` segment with steering off, `--bitwise`, every kind, one row in the record; the steered overhead table and the latest `402` KPIs collected in one place, with their intervention identity.
- A go/no-go list at the end: each item with its command, model, date and output, and any loss named by kind and interval.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None. This change verifies behaviour the series' specs already state; it adds no requirement (`skip_specs`).

## Impact

- `speed-bench/perf-record.md`: one A/B row, steering off, against the segment start.
- `docs/upstream-prs.md` or `dir-steering/README.md`: the collected results table.
- Model time: roughly two hours, one process at a time. Runs after the last of `401` to `405` has landed, or on request after any of them.
