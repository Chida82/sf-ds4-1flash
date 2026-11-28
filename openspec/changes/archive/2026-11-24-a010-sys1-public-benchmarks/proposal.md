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

- Converters for three public sources into the `820` item format: jevbench,
  the jevify policy suites, and seven suites of system-one-bench (real
  datasets with human labels: AG News, BoolQ, SST-2, SST-5, XNLI English and
  French, DAIR Emotion), rebuilt item for item and checked against its hashes.
- Full runs in three modes: plain readout, readout with a temperature fitted
  on held-out items, and the model's own answer after medium-effort reasoning
  (the reasoning is not part of the answer) on jevbench, the jevify policy
  suites and the first 30 items of each system-one-bench suite.
- typed-decisions (teacher-model labels) and jevify `long-state-24` (no
  published figures) are left out of the verdict (owner, 2026-11-19).
- Four fixed references on every set: Jev 1.13.0, CLM-8B, the best
  Qwen-derived system and Rizzo Flow, with an empty cell where one has no
  published figure, plus the best other non-DeepSeek figure.
- A quantization check: our thinking answers on the jevbench public items
  against the same model's full-precision production API, item by item.
- `sysone-bench/record.md` gains "Public benchmarks": our scores with
  intervals beside each reference, and a verdict per set and overall.

## Non-goals

- No change to the readout, template or server.
- Sets with more than 26 options per question (CLINC-150, Banking77) wait for
  `a040`; they are listed in the record as "not run: needs `a040`".
- No reproduction of other systems: their numbers are quoted as published.
- No jevbench sealed set: it needs a public endpoint, which the owner does
  not want now.
- No DeepSeek system as a reference: the API run serves only the
  quantization check.

## Impact

- `sysone-bench/convert.py`: two more sources. `sysone-bench/run.py`:
  `--effort` and token counts. `sysone-bench/jb_compare.py` (new).
  `sysone-bench/record.md`, `docs/system-one.md` section 8.
- About four hours of model time (2 h of it the thinking runs).
