# Proposal

## Why

Every question suffix token costs about 31 ms, and `915` measured that a
decision is bound by that per-token compute, not by SSD reads (read wait is
7% of a short decision): removing suffix tokens is the cheapest latency lever
left. Template version 1 (`800`, probe winner T-C) spends 28-45 tokens per
question, and about 20 of them are fixed text, not the question:
`\n\nQuestion: `, `\nOptions:\n`, the instruction line `Answer with the
identifier only.`, the chat markers. The `800` token dump also shows a
tokenization artefact: `"\n\nQuestion: "` is tokenized on its own, so its
trailing space becomes a lone token (id 223) and the instruction text starts
without its leading space, a split the model never saw in training.

The rule that pieces are tokenized separately exists only for the boundary
between the state and the suffix (so the state stays a token prefix). Inside
the suffix nothing requires it.

Removing ten fixed tokens saves about 0.3 s per question on the default
layout, which `a015` does not replace: `a015` is opt-in and gives up strict
isolation.

## What Changes

- Four suffix candidates (D1-D4) beside version 1 (D0), selectable at run
  time by a template id, so the probe and the bench run them from one build.
- A probe on the 12 fixtures, then the `820` bench on the Italian fixtures and
  the 500-decision typed-decisions subset, for D0 and every surviving
  candidate.
- A numeric gate (`sysone-bench/template_gate.py`). The winner becomes
  template version 2 and the server default; version 1 stays selectable with
  `--sysone-template 1`. With no winner, the code edits are reverted and only
  the record stays.
- Calibration files bind to the template version in use (the field exists
  since `820`); `fit.py` writes the version it is told.

## Non-goals

- No change to the state prefix (it is `830`'s cache key).
- No change to the live layout of `835` (`sf_sysone_turn_text`), nor to the
  `gen`/`think` wording in `run.py` (`template_prompt`).
- No schema-first layout (`a015`), no option trie (`a040`).
- No engine edit: `ds4.c`, `ds4_metal.m`, `ds4.h` are not touched.

## Impact

- `sf_sysone.c/.h`: a template id carried by `sf_sysone_open`, the suffix
  built per id.
- `ds4_server.c`, `ds4_help.c`: `--sysone-template N`; the `sf` object's
  `template_version` and the calibration check use the id in use.
- `tests/test_sysone.c`: `--suffix-probe` mode; the checks run for each
  frozen version.
- `sysone-bench/template_gate.py` (new) and its unit test in
  `tests/test_sysone_bench.py`; `sysone-bench/fit.py` gains
  `--template-version`.
- `sysone-bench/record.md`, `docs/system-one.md` section 7.
- About 4 hours of model time.
