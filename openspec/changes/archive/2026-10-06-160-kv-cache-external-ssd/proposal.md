# Proposal

## Why

The server's disk KV cache is the only thing that writes to an SSD during inference; model weights and Engram are read-only. The internal SSD is soldered to the board, the external one is replaceable. If `140` or `150` keeps the external SSD in the normal setup, moving the KV cache there trades a small, measured cost for less wear on a part that cannot be replaced.

## What Changes

- No runtime code. `--kv-disk-dir` already accepts any directory, and every eviction input (hits, last use, creation time, reason, tokens, context) lives in each `<sha>.kv` header, so a plain move preserves the cache and its eviction state.
- Measure server requests with the KV cache on the internal versus the external SSD, with the kept `140`/`150` placement active in both arms, so writes and loads compete with the external weight reads they will meet in use.
- Owner-set acceptance: an end-to-end cost down to -0.2% is accepted for the wear benefit. Below that, the documentation is not changed and the measured percentage per shape is reported to the owner, who decides.
- If accepted, `README.md` gains the command to run the server with the KV cache on the external SSD and the one-time move of an existing cache; the per-child suggested path in `AGENTS.md` and `docs/SERVER.md` follows.
- Starts only if `140` or `150` kept an external-SSD placement. Otherwise the external drive is not part of the normal setup and the change closes with a note.

## Capabilities

### New Capabilities
None. Documentation and measurement only (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `README.md`, `docs/SERVER.md`, `AGENTS.md` (suggested `--kv-disk-dir`), `speed-bench/perf-record.md` (a diagnostic section, not a harness row: `ab_bench.py` does not drive the server).
- Uses the existing `speed-bench/serve_concurrency_bench.py`. No change to `ds4_kvstore.c` or the server, so no upstream sync cost and no parity run.
- Needs the external SSD connected, with the `140`/`150` replica in place.
