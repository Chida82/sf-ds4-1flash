# Proposal

## Why

A chat-turn append of 256-1000 tokens runs as one layer sweep (`770`), and
that sweep costs 6.0-6.7 s whatever its length (perf-record, 770: 256 rows
6.5 s, 1000 rows 7.0 s). The time is expert delivery, not compute: every
layer fills its explicit buffer with all 384 routed experts (3.56 GiB), about
44% blitted from the decode cache and 56% read from the SSD (perf-record,
100), whether or not any row of the sweep selects them.

If a short sweep selects only a fraction of a layer's experts, delivering
only those would cut most of the sweep (change `790`). Nothing in the record
says how many it selects:

- "128 rows touch most of a layer's experts" (perf-record, Rejected ideas,
  the `530` row, and the 530 section) is a parenthesis, never counted, about
  cold sweeps with an empty cache.
- `310` measured that one extra row of the same user costs +5 expert misses
  over 40 layers at `82GB`, about 2% of its 240 selections. That points the
  other way: the uncached experts a short append needs may be few.
- `docs/upstream-prs.md`, `ee7e840`, closes "read only the selected experts"
  for sweeps of 8192 rows or more. It says nothing about 256-1000 rows.

This change counts. It writes no delivery code.

## What Changes

- A probe, `DS4_METAL_V41_PREFILL_SELECTED_STATS=1`, prints one line per layer
  of a single-tile sweep that uses the explicit expert buffers: rows,
  distinct selected experts, distinct selected experts that were not in the
  decode cache when the layer's delivery started, and experts not in the
  cache. Off by default; with it off nothing changes.
- Four counting runs (two contexts, two other texts) at the harness cache
  (`82GB`) with appends of 256, 300, 512 and 1000 rows.
- A verdict by fixed numbers (design, Gate): go for `790`, no-go with a
  Rejected ideas row, or a grey zone reported to the owner.
- The uncounted "128 rows touch most" statements in the record are replaced
  by the measured figures.

## Capabilities

### New Capabilities
- `prefill-expert-delivery`: which routed experts a prefill sweep delivers to
  its layer buffers, and what it reports about them. This change adds only
  the report; `790` adds the delivery rule.

### Modified Capabilities
None.

## Impact

- Code: `ds4.c` (a counting helper and one call in
  `ds41_graph_prefill_sweep`), `ds4_env.def`, `tests/test_deepseek41_prefill.c`.
  Under 60 runtime lines.
- Output: unchanged, bitwise. The probe reads a tensor the sweep already
  reads on the CPU (`ds41_prefill_seed`) and prints.
- Speed: none claimed. The default path gains one environment read per
  sweep, so no harness A/B and no parity run are owed (opt-in change, default
  path unchanged).
- Docs: `speed-bench/perf-record.md` (a section, and the Rejected ideas row
  if the verdict is no-go), `AGENTS.md` is not touched.
