# Proposal

## Why

In a CLI chat at `--ssd-streaming-cache-experts 80GB`, an 891-token second
turn prefilled at 27.4 tokens/s and a 327-token one at 28.1 (2026-11-07), the
decode rate: both ran token by token. The rule is upstream's, in
`ds41_prefill_count`: once a session holds context (`g->pos > 0`) and the
expert cache has at least half of all routed experts (7680 slots; `80GB` has
7810, `82GB` 8026), any remainder under 1024 tokens runs token-major ("warm
short appends beat a full disk sweep").

On this machine they do not:
- token-major costs about 36 ms per token at the decode rate, so 891 tokens
  cost about 33 s;
- one layer sweep has a nearly fixed cost: `append +1500`, a 1500-token sweep
  on a 5000-token context, took 5.7-7.8 s (README, 2026-11-07);
- the break-even is therefore far below 1024 tokens, roughly a few hundred.

It is not only short chats. The same rule decides the tail of every prompt
once the session holds context: a 2049-8191-token remainder whose last tile
has 1-255 rows, and the remainder of any prompt over 8192 whose last tile is
under 1024 rows (`8192 + 308` prefills 8192 rows in one sweep and 308 token
by token). Per-token cost grows with the context (attention over more keys),
so the loss grows with it too.

## What Changes

- Measure the cost of an N-token append, token-major against one sweep, at
  2K and at 8K of context, for N from 64 to 1000, at the README cache
  (`80GB`) and at the harness cache (`82GB`). The first token after the
  append counts: a sweep leaves the decode cache colder.
- Lower the warm minimum of `ds41_prefill_count` under single-box SSD
  streaming to the measured break-even. Resident and TP paths keep
  upstream's values.
- `DS4_METAL_V41_WARM_APPEND_MIN=<rows>` (tuning) sets the warm minimum;
  `1024` restores upstream's schedule.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `prefill-schedule`: the warm minimum for appends under SSD streaming.

## Impact

- Code: `ds4.c` (`ds41_prefill_count`), `ds4_env.def`.
- Output: changes for the appends that switch path. Batched and token-major
  kernels round differently, so these appends no longer match upstream's
  tokens; both paths are the model's own kernels and are tested exact
  against their references. The parity oracle's prompts are a few dozen
  tokens each plus one 5025-token prompt that runs as one medium sweep, so
  none reaches the changed rule.
- Speed: chats and prompt tails of 256-1023 tokens (or the measured range)
  prefill in seconds instead of tens of seconds. The harness `append +300`
  is exactly this case.
