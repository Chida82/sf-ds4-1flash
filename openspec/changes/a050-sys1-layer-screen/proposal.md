# Proposal

## Why

Two questions decide whether any "fewer layers" or "CLM-style" design is
worth engine work, and both can be answered **without editing the engine**:

1. *At which layer does the model already know the answer?* (`a055` needs
   this before it edits `ds4.c`.)
2. *Does a similarity readout work on this model's hidden rows, and at which
   layer?* This is the owner's question about CLM (Contrastive-LM): a frozen
   encoder, a state vector, cached option vectors, a dot product
   (`docs/system-one.md`, section 5).

A session snapshot already contains, as plain `float32`, one 512-value row
per layer for each of the last 128 positions: the key/value row that position
published at that layer, a normed linear view of the layer's attention input.
`ds4_session_save_snapshot` is public API. So one ordinary full-depth run
yields a per-layer vector at the readout position for all 40 layers.

Trained CLM heads are out of reach here (its heads use about 90M training
pairs; this Mac produces thousands of decisions a day, enough for class
centroids and one temperature). What can be measured is the untrained
variant and a centroid readout, layer by layer.

## What Changes

- `sysone-bench/sf_capture.c`: a model-backed tool on the public API. For
  each decision it records the teacher's option logits (the `800` readout)
  and the 40 × 512 rows at two positions; for each option text it records the
  40 × 512 rows of that text encoded alone.
- `sysone-bench/screen_fit.py` (standard library): two analyses per layer.
  - **A, in-context probe**: answer-symbol centroids on the readout row.
    Agreement with the teacher for every layer 0-39.
  - **B, similarity readout (CLM-raw by layer)**: centred cosine between the
    row at the end of state + question and the rows of the option texts
    encoded alone.
- A table per analysis in `sysone-bench/record.md` and a verdict for `a055`.

## Non-goals

- No edit to `ds4.c`, `ds4_metal.m`, `ds4.h` or the server.
- No trained projection heads.
- No product feature: this change produces two tables.

## Impact

- New files under `sysone-bench/`; one `Makefile` rule.
- About one hour of model time.
