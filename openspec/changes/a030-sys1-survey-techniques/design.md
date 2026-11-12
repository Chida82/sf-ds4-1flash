# Design

Depends on `810`, `820`, `835` (for `sf_sysone_turn_text` and
`sf_sysone_answer_suffixes`). Read `docs/system-one.md` section 11 first. Do
not edit `ds4.c`, `ds4_metal.m` or `ds4.h`.

## Probe 1: rotation averaging (no new model code)

Inputs: two `run.py --mode sysone` result files on the full typed-decisions
`choice` items, `--rotate 0` and `--rotate 1` (run them; `820`'s were a
150-item subset).

`sysone-bench/rotation_avg.py --a R0.jsonl --b R1.jsonl [--temperature T]`
prints, with state-level bootstrap intervals from `metrics.py`:

- accuracy and NLL of rotation 0, of rotation 1, of the mean of the two
  probability vectors (per option **name**);
- for thresholds 0.5, 1, 1.41, 2, 3, 5 on rotation 0's top-two logit gap:
  share of items re-asked, accuracy and NLL when only those are averaged.

Run it raw and with the fitted `choice` temperature. Unit test: two synthetic
files where rotation 1 fixes a planted position bias.

Rule: **keep** (write a follow-up change for a server option
`"sf":{"rotate_below":G}`) only if some threshold re-asking at most 30% of
items gains at least 2 accuracy points with an interval excluding zero, or
lowers calibrated NLL by at least 0.05. Otherwise record "rotation averaging
dropped: calibration and `a020` cover it" with the table.

## Probe 2: chained questions

### Layout

Question 0 is asked exactly as today (template suffix). After reading
question k, the sequence continues, for question k+1:

1. the placeholder token: the single token of `"-"` (assert at
   `sf_sysone_open` that `"-"` is one token);
2. `ds4_token_eos(e)`;
3. `ds4_token_user(e)`;
4. `ds4_tokenize_text` of `sf_sysone_turn_text(&q[k+1])`;
5. `ds4_chat_append_assistant_prefix(e, &t, DS4_THINK_NONE)`.

Then `ds4_session_sync` to the new end and read out as `800` does. No
snapshot is saved or restored.

```c
/* Questions asked in sequence in one conversation; question k sees the text
 * of questions 0..k-1 and a "-" in place of their answers. Not isolated. */
int sf_sysone_answer_chained(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                             const sf_sysone_question *q, int n_questions,
                             const double *temperature, sf_sysone_answer *answers,
                             char *err, size_t errlen);
```

Server: `"sf":{"chain":true}` selects it for `state` requests (422 together
with `live`). The `sf` object reports `"layout":"chained"`. Calibration files
are bound to a layout: with `chain` the server uses temperature 1 and says
`"calibrated":false`.

### Checks

- model-backed, in `tests/test_sysone.c` (`make test-sysone`): question 0's
  logits chained are bitwise equal to the same question asked alone (named
  line `sysone: chained first question == isolated, bitwise`);
- the same chained request twice is bitwise equal.

### Bench

typed-decisions states carry several questions each (`run.py` already sends
one request per state). Run all states isolated and with
`--sf '{"chain":true}'`; also chained with the questions in reverse order
(add `--reverse-questions` to `run.py`) to see order effects.

Report per position in the chain (0, 1, 2, ...): accuracy isolated against
chained, with intervals; top agreement between the two; total ms per state.

Rule:
- **keep the layout as an option** if chained accuracy over positions 1 and
  later is within 1 point of isolated (interval including zero) in both
  orders. Then write, in the record, the expected gain of a multi-row sweep
  readout: questions per state at which `6.3 s` beats `31 ms × chained
  tokens`, and say that a change for it (reading logits at several rows of one
  sweep; the decoder-suffix optimisation computes only the last token's rows
  today) is justified for requests above that count.
- **drop** if it loses more than 1 point in either order: remove the server
  option and the function, keep the record.

## Probe 3: graded `noul`

A second `noul` suffix, selected by `"sf":{"noul":"graded"}`:

- option lines replaced by one line:
  `Rate from 1 (certainly no) to 9 (certainly yes).`
- instruction line: `Answer with the digit only.`
- readout over the digit symbols `1`..`9` (already verified single tokens);
  `p_i` their restricted softmax; `noul = Σ ((i − 1) / 8) · p_i`;
  `legal_mass` over the nine digits.

`criteria.true` / `criteria.false`, when present, are written before the
rating line as `Yes means: ...` / `No means: ...`.

Bench: all `noul` items of typed-decisions and the fixtures, two-letter
against graded: accuracy at threshold 0.5, NLL, ECE, raw and with a
temperature fitted on the even-id half (for graded, fit the temperature on
the nine logits before the expectation).

Rule: **keep as the default `noul` readout in a new template version** if raw
ECE falls by half and accuracy is within 1 point; **keep as an option** if
only calibrated NLL improves by 0.02; otherwise drop it and remove the code.

## Editing `a035`

Add to `a035-sys1-confidence-escalation/design.md`, under "Request option":
`"max_share": 0.2` (optional, default 0.2): at most that share of a
request's questions escalate, the lowest top probabilities first; and to its
unit-test task: the cap on a five-question request escalates one.

## Risks

- Chained answers depend on question order by construction; the reverse run
  measures it and the docs must say "not isolated".
- A rating scale may push answers to the middle; ECE and accuracy at 0.5
  show it.
