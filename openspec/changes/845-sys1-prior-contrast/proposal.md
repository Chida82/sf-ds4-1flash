# Proposal

## Why

Three published techniques are the same formula once restricted to the
option symbols: contextual calibration, context-aware decoding (CAD) and
classifier-free guidance all compute

```
p = softmax( (z − β · z0) / T )
```

where `z` are the option logits with the state and `z0` the option logits of
the same question **without** the state. `840`'s prior correction is the
single point β = 1. Nothing says 1 is the right strength for this model; the
literature reports cases where a full subtraction hurts.

Fitting β costs no engine work and no time per request: `820` already fits T
on held-out items, and `z0` is either cached per schema (`840`) or can come
for free from other requests' answers to the same question (a "batch
prior": the mean option log-probabilities of that question over other
states).

No contrast makes a decision faster. This change can only move accuracy,
calibration and the flip rate under option rotation, and it is kept only if
it does.

## What Changes

- `run.py --blank-state`: the same items with the state replaced by
  `(no state given)`, one request per distinct question.
- `sysone-bench/contrast_fit.py`: fits β per question type for two priors
  (content-free and batch), reports held-out NLL, accuracy and rotation flip
  rate against β = 0.
- If the gate passes: `prior_beta` per type in `calibration.json`, applied by
  `sf_sysone_finish` on top of `840`'s cached prior.

## Non-goals

- No new readout, no engine edit.
- No layer contrast here (it is an offline table in `870`).
- No server-side batch prior store unless the owner asks after seeing the
  numbers.

## Impact

- `sysone-bench/run.py`, new `contrast_fit.py`, record.
- If kept: one multiplication in `sf_sysone.c`, one field in the calibration
  file and its loader in `ds4_server.c`.
