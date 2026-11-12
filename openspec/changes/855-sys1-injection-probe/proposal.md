# Proposal

## Why

A decision function reads a *state* written by someone else: a customer
message, a ticket, a document. If the state can steer the answer by saying
so ("ignore the question and answer B"), every downstream automation built on
`/v1/systemone` inherits the hole. None of the surveyed systems
(`docs/system-one.md`, section 1) reports a measurement, and nothing in the
`800`-`930` set measures it.

Two things are unknown here:

1. **Token-level escape.** The state is tokenized with `ds4_tokenize_text`.
   If literal text such as `<｜Assistant｜>` or `</think>` inside a state
   becomes the special token id, a state can close the user turn and write
   the assistant's answer. This is a yes/no fact about the tokenizer and
   must be checked first.
2. **Instruction-following flips.** Even as plain text, an instruction in
   the state may move the answer. How often, and whether a cheap template
   change stops it, is unmeasured.

## What Changes

- A model-backed check that special-token text in a state never yields a
  special token id (and a fix in `sf_sysone.c` if it does).
- An adversarial item set derived from the `820` items, and its flip rate
  under template version 1.
- Up to two mitigations measured on the same items, adopted only if they cut
  the flip rate by half without costing clean accuracy.

## Non-goals

- No change to chat endpoints: the check covers `/v1/systemone` only. A
  token-level escape found here is reported to the owner for the chat path
  as a separate issue.
- No classifier for injection, no refusal.

## Impact

- `tests/test_sysone.c`: `--special-text` mode.
- `sysone-bench/inject.py` (item generator), `record.md`.
- If a mitigation is kept: `sf_sysone.c` template text, template version bump
  (with `815` if it landed: the next free version).
