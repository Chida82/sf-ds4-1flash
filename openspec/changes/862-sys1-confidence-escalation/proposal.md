# Proposal

## Why

`860` makes thinking a per-request dial: N reasoning tokens before the
readout, for every question of the request. Thinking costs about 31 ms per
token, and most questions do not need it: on the `800` fixtures eleven of
twelve answers had confidence 1.000. Spending N tokens on every question to
fix the few uncertain ones wastes nearly all of it.

The readout already says which questions are uncertain: confidence (Jev's
formula) and, after `820`, a calibrated top probability. Re-asking only the
questions below a threshold with `860`'s think path buys most of the accuracy
gain for a fraction of the cost. No surveyed system does this; it needs no
engine code.

## What Changes

- A request option `"sf":{"escalate":{"below":C,"think":N}}`: answer every
  question with the plain readout; re-answer the questions whose calibrated
  top probability is under `C` with `860`'s bounded think of `N` tokens; the
  response carries the escalated answer and marks it.
- A server default (`--sysone-escalate C:N`, off by default) for clients that
  cannot send `sf`.
- A bench sweep over `C` that reports accuracy and mean latency per decision,
  and the chosen default.

## Non-goals

- No change to the plain readout or to `860`'s think path.
- Not a replacement for `860`'s "think once, answer many": that path stays
  for requests that ask for it.

## Impact

- `ds4_server.c`: option parse, the second pass in `sysone_job`, response
  marks, the flag (`ds4_help.c`).
- `sf_sysone.c`: none if `860` exposes its think path per question; else one
  wrapper.
- `sysone-bench/run.py`: `--sf` already passes the option; a sweep script.
