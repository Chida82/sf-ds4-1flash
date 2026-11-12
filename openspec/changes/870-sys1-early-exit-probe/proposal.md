# Proposal

## Why

The owner asked whether layers can be removed for decisions, and doubts it.
A layer at position t reads only lower layers, so a readout taken at layer L
never needs layers above L **for any token**: state prefill included, a
request would cost about L/40. No other change in this series can cut the
state prefill.

Two cheaper screens come first and decide whether this change starts at all:

- `865` screens every layer from session snapshots, with no engine edit.
- Stage 0a here measures whether a token that stops at layer L really costs
  about L/40. If it does not, no design that runs fewer layers pays, whatever
  its accuracy, and the change stops after ten minutes of model time.

Against: the answer symbol is a token-level fact the last layers are trained
to produce. Published work on multiple choice (arXiv 2407.15018) finds the
answer fixed in a few middle layers and only raised in vocabulary space by
late ones, so a *raw* readout low in the stack is unlikely to work, and a
*fitted* readout might.

This change is research with stage gates. It ends with a number and a
recommendation, and ships no speed-up by itself.

## What Changes

- A probe `DS4_V41_EXIT_LAYER=L`: the token-major step runs layers 0..L−1,
  hands the last executed block's stream weights to the output head, and
  reads the logits there. Four edits in `ds41_graph_step`.
- Stage 0a: milliseconds per token at L = 12, 20, 28, 40 in one long-lived
  process per L.
- Stage 0b: accuracy, agreement with L = 40, and legal mass at
  L = 40, 36, 32, 28, 24, 20, 16, 12, 8.
- Stage 1 (by the gate): capture the head's input row at L, fit three small
  translators offline (bias and temperature; answer-symbol centroids; a ridge
  probe), and measure held-out agreement.
- An offline by-product: the layer contrast `z40 − β·zL` on the option logits
  (the DoLa idea), computed from the stage 0b files with no extra model time.
- A written recommendation: stop, or a follow-up change that makes an exit
  layer a property of a session, which is not routine work on `ds4.c`.

## Non-goals

- No early exit on production paths. With the variable unset the build's
  output is bitwise unchanged.
- No sweep-path truncation: the probe forces token-major prefill and is used
  on states under 250 tokens.
- No all-layers-in-one-pass lens. It was designed and verified as feasible
  (30-40 lines, a drain per layer on the readout token, a trigger from
  `ds4_session_sync`), but it is not three lines and it cannot produce the
  timing column. The owner may ask for it as a separate change.

## Impact

- `ds4.c`: four edits in `ds41_graph_step`, plus the env read; `ds4_env.def`.
  Stage 1 adds one optional readback in `ds41_graph_logits`.
- `sysone-bench/`: `lens_fit.py`, runs, record.
- A new permanent sync-conflict site in `ds41_graph_step`; removed again if
  the recommendation is "stop".
