# Design

Depends on `800`, `810`, `820`. Read `docs/system-one.md` section 7 and the
`--tokens` output of `tests/test_sysone` first.

## Candidates

All keep the state prefix of version 1 unchanged. `Q` is the question
instructions, `L_i` the option lines of version 1 (`A. name: text`).

| Id | Suffix text before the chat markers | Tokenized as |
|---|---|---|
| D0 | version 1: `\n\nQuestion: ` · `Q` · `\nOptions:\n` · `L_i`... · `Answer with the identifier only.` | pieces (as today) |
| D1 | same text as D0 | one string |
| D2 | `\n\nQuestion: Q\n` + `L_i`... + `Answer with the identifier only.` (no "Options:" header) | one string |
| D3 | `\n\nQuestion: Q\n` + `L_i`... (no instruction line) | one string |
| D4 | `\n\nQ\n` + `L_i`... (no header word at all) | one string |

After the text, every candidate appends `ds4_chat_append_assistant_prefix(e,
&t, DS4_THINK_NONE)`, as version 1. One string means: build the text with
`snprintf` into a growing buffer and call `ds4_tokenize_text` once; the chat
markers are still appended as token ids (never as text).

A `noul` question's `Q` is the statement; a `score` question keeps its digit
symbols. No candidate changes symbols.

## Runs

1. `tests/test_sysone MODEL --probe` with D0-D4 on the 12 fixtures: print per
   candidate correct count, mean and minimum legal mass, mean suffix tokens.
   Any candidate with minimum legal mass under 0.9 is dropped here.
2. For the survivors, the `820` bench (`run.py --mode sysone`) on
   `fixtures-it.jsonl` and the `typed-decisions` test split, through a server
   started with `--sysone-template` set to a scratch build of each candidate
   (build the candidate as template version 2 in a scratch copy; never
   publish more than one version 2).

## Gate (in this order)

A candidate is acceptable when, against D0 on the same items:
- accuracy is not lower by more than 1 point (paired bootstrap interval from
  `820`'s `metrics.py`);
- NLL is not higher by more than 0.02 nats;
- mean legal mass is at least 0.99.

Among acceptable candidates pick the fewest mean suffix tokens; break a tie
by lower NLL. If none is acceptable, record the table and keep version 1.

## Freezing

The winner is `SF_SYSONE_TEMPLATE_VERSION 2`. `sf_sysone_open` takes the
version (1 or 2); the server flag `--sysone-template` selects it, default 2.
A calibration file bound to version 1 refuses to load with version 2 (the
`820` binding check already names the field). Re-fit the calibration for
version 2 with `fit.py` and record both.

## Risks

- Fewer instruction tokens can shift the prior over options (fewer words
  telling the model what to do). NLL and the `820` rotation flip rate catch
  it; record the flip rate per candidate too.
