# Proposal

## Why

A System One endpoint on a 340 GiB model costs 3-4 s per decision where a 4B
model answers in 50 ms. That is worth having only if the answers are better.
`820` measured one public set on a 100-state subset (0.682 against published
0.727-0.741 for Jev and for stock 27-31B models read the same way), which is
not enough to say whether this model is ahead, level or behind.

`docs/system-one.md` section 11 lists the public benchmarks other projects
report on, with their scores. This change runs the ones that can be
downloaded and are licensed, in the others' conditions, and writes one table
and a verdict.

## What Changes

- Converters for three public sets into the `820` item format.
- Full runs (not subsets) in three modes: plain readout, readout with a
  temperature fitted on held-out items, and the model's own thinking answer on
  a sample.
- `sysone-bench/record.md` gains "Public benchmarks": our scores with
  intervals beside each published score, and a verdict per set and overall.

## Non-goals

- No change to the readout, template or server.
- Sets with more than 26 options per question (CLINC-150, Banking77) wait for
  `a040`; they are listed in the record as "not run: needs `a040`".
- No reproduction of other systems: their numbers are quoted as published.

## Impact

- `sysone-bench/convert.py`: two more sources. `sysone-bench/record.md`,
  `docs/system-one.md` section 8.
- About four hours of model time.
