# Proposal

## Why

With the state-first layout every question pays its whole text at 31 ms per
token: instructions and options are typically 30-60 tokens, so 1-2 s per
question, and ten questions cost more than the state. The surveyed systems do
not care, because a suffix token costs them microseconds. Here it is the
largest term after the state.

The opposite workload is also the common one in production: **the same
questions asked of many different states** (classify every incoming ticket
with the same schema). State-first shares nothing across such requests.

Putting the question definitions *before* the state fixes both. The schema
becomes a cacheable prefix shared by every state; each question's suffix
shrinks to a pointer of about 8 tokens (0.25 s). No surveyed system does
this: with causal attention it gives up strict isolation (a question's
definition is visible while another is answered), which Jev promises. So it
is an opt-in layout, accepted only if the bench shows it costs no accuracy.

The schema prefix also makes a known debiasing trick nearly free. Reading
each question's option logits once with an empty state gives the model's
prior over the symbols (position and label bias); subtracting it is
"contextual calibration". State-first would pay a full extra question per
request for it; here it is one readout per schema, cached.

## What Changes

- Layout `schema_first`: system turn, then all question definitions, then the
  state, then per question a short pointer suffix and the readout.
- Selected per request with `"sf":{"layout":"schema_first"}` or server-wide
  with `--sysone-layout schema_first`. Default stays `state_first`.
- A schema cache: the snapshot after the definitions, keyed by their tokens,
  reused for every state.
- Optional prior correction, `"sf":{"prior_correction":true}`: per-question
  option priors measured once per schema and subtracted from the logits.
- Bench runs that decide both: accuracy and ECE against state-first, latency
  per question, flip rate under rotation with and without the correction.

## Non-goals

- Not the default, and not offered as Jev-compatible isolation.
- No chaining of answers: a question never sees another question's *answer*,
  only its definition.

## Impact

- `sf_sysone.c/.h`: second layout, template version field per layout.
- `ds4_server.c`: request option, flag, schema cache beside the state cache.
- `sysone-bench/`: runs and record.
- Calibration files carry the layout in their binding (already a field).
