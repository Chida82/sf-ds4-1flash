# Proposal

## Why

The model can answer a typed question without generating a token: prefill the
state and the question, then read the next-token logits of the option symbols.
`docs/system-one.md` (sections 1 and 3) shows this is what Rizzo Flow, JevK5
and the LLM-as-Jev paper do, and that it needs no training. This repository
has every primitive for it (`ds4_session_sync`, `ds4_session_save_snapshot`,
`ds4_session_token_logprob`) and no code that puts them together:
`docs/MODEL_KNOWLEDGE.md` lists "a classification head" under interfaces that
do not exist.

This change adds the engine-side core, with no HTTP: one C module that turns
(state, questions) into probabilities. `810` and every later System One change call it.

## What Changes

- New `sf_sysone.h` / `sf_sysone.c`. It uses only the public `ds4.h` API, so
  `ds4.c` and `ds4_metal.m` are not edited and no upstream sync conflicts.
- Prompt layout "state first": a state prefix shared by all questions, one
  question suffix per question, an assistant turn with thinking closed and a
  prefilled answer opening.
- Readout: softmax over the option symbols' logits; `noul`, `choice` (up to
  26 options) and `score` (up to 10 levels); Jev's confidence formulas; the
  legal mass as a health figure.
- Branching: the state is prefilled once, saved with
  `ds4_session_save_snapshot`, and restored before every question after the
  first. Questions never see each other.
- A template probe run once on the model picks the answer prefill among three
  candidates by legal mass; the winner is frozen as template version 1.
- `tests/test_sysone.c`: model-less checks in `make test`, model-backed checks
  in `make test-sysone`.

## Non-goals

- No HTTP endpoint (`810`), no calibration (`820`), no cache across requests
  (`830`), no more than 26 options (`a040`), no thinking (`a025`).
- No `box`, no images.
- No change to chat output: the engine sources are untouched.

## Impact

- New files: `sf_sysone.h`, `sf_sysone.c`, `tests/test_sysone.c`.
- `Makefile`: object rule, test binary, `test` list, `test-sysone` target.
- Docs: `docs/system-one.md` gains a "Template" section with the probe result.
