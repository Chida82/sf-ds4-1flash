# Design

Depends on `820`. The production step depends on `840` having been kept.

## Data

From `820`'s runs, per layout: `results.jsonl` with `sf.debug` logits
(`z`), with `--rotate 0` and `--rotate 1`. New: `run.py --blank-state`
replaces every state by the text `(no state given)` and sends one request
per distinct (instructions, options, rotation); its logits are `z0`.

`z0` must be read raw: no `sf.prior_correction`, no calibration file loaded
(or `"sf":{"temperature":1}`), same layout, same rotation. Under
`schema_first` the prior belongs to (schema, question index), because the
schema prefix holds every question of the request: blank the state inside the
same grouped request, do not regroup.

Cost: a blank-state request is a short state plus the suffix. Under
`state_first` about 2 s per distinct question; under `schema_first` the
schema prefill too when it is not cached (about 2 s per 60-token question).
The whole run is minutes.

## Fit (`contrast_fit.py`, standard library)

Notation: `c(v) = v − mean_k(v)` centres a vector over the options.
`T0` is `820`'s fitted temperature for the type (not 1).

- **Content-free prior**: `u = c(z0)` of the item's question.
- **Batch prior**: `u = c(mean over the other fit states of log-softmax(z))`
  for the same question; needs at least 8 other states, else the item is
  reported as "no batch prior".

`p_β = softmax((z − β·u) / T0)` for β in 0, 0.25, 0.5, 0.75, 1, 1.25, 1.5.
β = 0 is `820`'s calibrated baseline; β = 1 with the content-free prior is
`840`.

Split by **state** (even hash fit, odd hash test), never by item. Choose β
on the fit half by NLL; report on the test half, against β = 0, with paired
state-level bootstrap intervals (2000 resamples, fixed seed):

- NLL difference; accuracy difference;
- rotation flip rate (share of items whose top differs between `--rotate 0`
  and `--rotate 1`), with β applied to both rotations.

`score` is fitted and reported, but excluded from the gate: an ordinal prior
is information, not bias.

## Gate

Keep (write `prior_beta` into the calibration file) when, for `noul` or
`choice`, on the test half:

- the NLL interval of (β* − β0) lies wholly below 0 **and** the accuracy
  interval does not lie wholly below −1 point; or
- the flip rate falls by at least one third with the same accuracy condition.

Prefer the batch prior when its test NLL is within 0.01 nats of the
content-free prior: it needs no blank-state readout in any layout.

Drop (record a rejected row, change no code) when the best β gains under
0.01 nats and the flip rate does not fall.

## Production step (only on "keep", only with `840`)

- `calibration.json` gains `"prior_beta":{"noul":b1,"choice":b2}` (absent = 1,
  which is `840`'s behaviour).
- `840`'s line `logit'[k] = logit[k] − (prior[k] − mean prior)` becomes
  `logit'[k] = logit[k] − beta · (prior[k] − mean prior)`.
- Unit test: β = 0 reproduces the uncorrected answer bitwise; β = 1
  reproduces `840`'s.

A batch prior in production would need the server to remember past option
logits per question. Do not build it here; record its offline result and let
the owner decide.
