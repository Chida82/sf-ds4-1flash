# Proposal

**Level: senior.** Edits the decode step and the sync loop of `ds4.c`. Not
for the implementer of the changes that carry no level line.

## Why

`a055` measures a readout below the last layer by *stopping* the model at L:
one server process per L, token-major prefill only, states under 250 tokens,
about three hours for nine layers. But a layer never depends on higher
layers, so one normal full-depth pass already contains the exact
"stopped at L" state for every L: it is the residual at the top of layer L,
folded with the split weights layer L−1 left. Applying the output head there,
on the readout token only, gives all forty rows of `a055`'s table from one
ordinary run, **on states prefilled by the production sweep**. That last
point matters here: the prefill schedule moves logits by up to 1.37, and
`a055` can only measure the token-major schedule.

It also yields, per decision, the layer from which the top option stops
changing ("decision depth"), a candidate difficulty signal, and the data for
the layer contrast, with no extra run.

It does **not** replace `a055`'s timing gate: only a run that really stops at
L shows what a truncated token costs.

## What Changes

- A probe, on the readout token only: at the top of each layer L ≥ 1, drain,
  hand the previous block's split to the head's fold weights, apply the head
  into a side buffer, record the listed tokens' logits and the vocabulary
  log-sum-exp, resume.
- A trigger from `ds4_session_sync`: the probe fires for the last prompt
  token when that token runs token by token.
- An offline analysis: per-layer agreement, legal mass, decision depth
  against plain confidence, layer contrast.

## Non-goals

- No production feature. Unset, the build is bitwise unchanged.
- No sweep-path lens (the readout token of a decision is always token-major).
- No kernel. The production form (K dots per layer on the GPU) is described
  as a follow-up and needs a new read-only kernel that also returns the
  row's norm.

## Impact

- `ds4.c`: about 30-40 lines at two sites (`ds4_session_sync`,
  `ds41_graph_step`), one graph field, `ds4_env.def`.
- `sysone-bench/lens_curves.py`, record.
- Same conflict site as `a055` and `a065` in `ds41_graph_step`: land them in
  one order and keep the three hooks adjacent.
