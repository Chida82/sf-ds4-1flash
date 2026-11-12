# Proposal

## Why

`800` measured three questions of 35, 28 and 44 suffix tokens at 5.7 s
(short state) and 7.0 s (long state). At the documented 31 ms per token the
suffixes alone account for about 3.3 s, so 2.4-3.7 s per decision goes
somewhere nobody has measured: the snapshot save, the two restores, the first
token after a restore, or the readout. The same run prefilled a 38-token
state in 3.6 s, about 95 ms per token, three times the documented decode rate.

Every later System One change (`830`, `840`, `850`) multiplies branches. A
second spent per branch on something other than the suffix is the largest
cost after the state itself, and it is invisible today.

## What Changes

- `sf_sysone_answer` gains `restore_ms` and `eval_ms`; `sf_sysone_decide`
  reports `save_ms` through a new optional out-parameter struct
  `sf_sysone_timing` (state prefill ms, save ms). The server's `sf` object
  carries them.
- `tests/test_sysone --timing` runs a fixed matrix (state of 38 and 655
  tokens; 1, 3 and 6 questions) three times and prints one row per phase.
- A record in `docs/system-one.md` ("Branch cost"), and a decision: if save
  plus restores exceed 30% of the question phase, a follow-up is written
  naming the slow call; if the first tokens of a fresh state cost more than
  twice the decode rate, the cause is located (expert cache misses or
  first-token overhead) and recorded.

## Non-goals

- No engine edit in this change. Fixes go to a follow-up once the cost is
  located.
- No change to answers: the timing fields are additive.

## Impact

- `sf_sysone.h/.c`: two answer fields, one optional struct.
- `ds4_server.c`: the `sf` object gains the fields.
- `tests/test_sysone.c`: `--timing` mode.
- `docs/system-one.md`: "Branch cost" section.
