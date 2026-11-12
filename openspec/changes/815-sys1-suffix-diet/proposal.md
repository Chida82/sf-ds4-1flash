# Proposal

## Why

Every question suffix token costs about 31 ms (`docs/system-one.md`,
section 3). Template version 1 (`800`, probe winner T-C) spends 28-45 tokens
per question, and about 20 of them are fixed text, not the question:
`\n\nQuestion: `, `\nOptions:\n`, the instruction line `Answer with the
identifier only.`, the chat markers. The `800` token dump also shows a
tokenization artefact: `"\n\nQuestion: "` is tokenized on its own, so its
trailing space becomes a lone token (id 223) and the instruction text starts
without its leading space, a split the model never saw in training.

The rule that pieces are tokenized separately exists only for the boundary
between the state and the suffix (so the state stays a token prefix). Inside
the suffix nothing requires it.

Removing ten fixed tokens saves about 0.3 s per question on the default
layout, which `840` does not replace: `840` is opt-in and gives up strict
isolation.

## What Changes

- A second template probe over suffix variants, measured on the `820` bench
  (accuracy, NLL, legal mass, suffix tokens), not only on the 12 fixtures.
- The winner becomes template version 2 if it passes the gate; version 1
  stays selectable for calibration files bound to it.
- Calibration files bind to the template version (already a field in `820`).

## Non-goals

- No change to the state prefix (it is `830`'s cache key).
- No schema-first layout (`840`), no option trie (`850`).

## Impact

- `sf_sysone.c/.h`: template table with versions 1 and 2, a version argument
  carried by `sf_sysone_open`.
- `ds4_server.c`: `--sysone-template N` (default: the newest), the `sf`
  object's `template_version` reports the one used.
- `tests/test_sysone.c`: the probe table gains the candidates.
- `sysone-bench/record.md`, `docs/system-one.md` section 7.
