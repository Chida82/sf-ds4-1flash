# Proposal

**Level: expert.** A new layer-major sweep function in `ds4.c`, beside the
hottest and most upstream-churned function of the engine. It needs someone
who already knows the V4.1 prefill path. Ask the owner before starting.

## Why

`800` answers K isolated questions with K suffix branches, each at 31 ms per
token: ten questions of 45 tokens after a 1500-token state cost 6.9 + 14 s.
But a layer sweep's 6-7 s is *weight delivery*: each layer's experts are
read from the SSD whatever the row count, and an extra row costs 0.5-0.85 ms
(measured: 64 rows 6.2 s, 1000 rows 7.0 s). So if the K branches rode the
state's own sweep, the whole request would cost about one sweep: 7.7-8.5 s
instead of 21 s, and 30 questions about 8.5 s instead of 49 s.

The engine refuses multi-session batches under streaming, and K sessions
would not fit in memory anyway (about 8 GiB of context buffers each). The
route here is one graph, time-multiplexed **inside each layer**: run the
state tile, then each branch tile from the same starting state, restoring
between branches the few things a tile writes.

This is the only design in the series that makes the default, strictly
isolated, Jev-compatible path fast; `a015` is faster per question only by
giving up isolation. It also gives what `docs/system-one.md` lists as
unavailable: several independent short states answered in one sweep.

## What Changes

- `ds41_graph_fork_sweep`: a sibling of `ds41_graph_prefill_sweep` that takes
  an optional state tile and K branch tiles and returns each branch's
  last-row logits, leaving the session valid at the end of the state.
- A `ds4.h` entry point and its use by `sf_sysone` above a row-count
  break-even.
- A bitwise oracle against the existing single-branch path.

## Non-goals

- No chained tail (several open answer slots in one prompt): prior work
  shows untrained models degrade from the second slot on, and the fork gives
  the same latency with isolation.
- First version: state of at most 2048 new rows (no decoder-suffix
  shortcut), no images, no steering, single box.
- The chat sweep is not edited.

## Impact

- `ds4.c`: 150-250 new lines in one new function plus an entry point;
  `ds4.h`; a model-backed test.
- Calibration files bind to the path: sweep kernels round differently from
  token-major ones.
