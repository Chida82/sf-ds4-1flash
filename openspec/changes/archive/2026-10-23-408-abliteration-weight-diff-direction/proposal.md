# Proposal

## Why

Abliteration removes a model's refusal behaviour by editing weights: it projects the
residual-writing matrices against a refusal direction `r` (`W' = W - r (r^T W)`). The
difference between an abliterated checkpoint and its original therefore is, per edited
matrix, rank-one along exactly `r` (`ΔW = W - W' = r (r^T W)`), so the left singular
vector of `ΔW` recovers the removed direction per layer — a high-quality refusal
direction read straight from what a working abliteration took out, entirely offline, with
no activation collection, no generation and no GPU. Public abliterated V4.1 checkpoints
exist (`audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF`, Q2, from the same ds4 project as
our model; `distributedcognition/DeepSeek-V4.1-Flash-abliterated`; a domain variant
`drowzeys/DeepSeek-V4.1-Flash-Abliterated-Cybersecurity-Unleashed`). A weight-diff
direction is a candidate to compare against, and possibly improve on, the activation-
derived `msuiche` vector `402` validated.

## What Changes

- Acquire a comparable abliterated checkpoint and diff it against our base weights at the
  residual-writing sites, layer by layer, recovering the removed direction (SVD of `ΔW`)
  as a per-layer unit-norm candidate in the existing f32 direction format.
- Require same-quantization comparability. Our model is a plain `Q2` from
  `antirez/deepseek-v4.1-flash-gguf`; the diff uses the matching plain-`Q2` abliterated
  file so `ΔW` is the edit, not a requantization difference. A base-match sanity check
  (an un-edited tensor must diff to ~0) gates trust in the result before any direction is
  published.
- Report the recovered direction's geometry against the `402` `msuiche` vector (per-layer
  cosine, rank, which layers carry a nonzero edit) and, where the quantization permits,
  the edited-site map. Geometry is evidence of what abliteration targeted, not proof of
  efficacy.
- Evaluate a recovered candidate through the `402` axis-A harness at a finishing token cap
  against the `msuiche` baseline. A candidate that is ill-formed, not comparable
  (sanity check fails), or no better than `msuiche` is a valid completion recorded as
  such; nothing is adopted as a default here.
- Survey the domain variant (`drowzeys` cybersecurity) for any additional or
  domain-specific edited direction, as an analysis task, not a commitment to use it.

## Capabilities

### New Capabilities
- `abliteration-weight-diff`: recovering a refusal/steering direction from the weight
  difference between an abliterated checkpoint and its original, validating comparability,
  and comparing it to the activation-derived vector — a weight-space derivation method
  distinct from the activation-contrast method.

### Modified Capabilities
<!-- none: reuses the 402 harness and the existing f32 direction format without changing
     their requirements. -->

## Impact

- `dir-steering/` tooling: a new offline GGUF weight-diff/dequantization step emitting an
  f32 candidate; no change to existing candidates or the runtime hook.
- Shared Hugging Face cache: downloads one abliterated Q2 GGUF (~340 GiB) via `hf
  download`; never copied into the repo (SPEC.md §C).
- `eval/` (402 harness): reuses the axis-A arm and `--max-tokens`; the evaluation of a
  recovered candidate is harmful axis-A and stays user-run.
- Depends on `402` (acceptance harness). Independent of `403`/`404`/`405`/`407`, though a
  recovered direction could feed `404` fusion or `407` composition later.

## Closure (2026-10-23) — measured to the end, and it loses

The weight-diff method works: differencing a baked abliterated checkpoint against our own quant
recovers a clean global direction, and it corroborated the external one independently (cosine 0.71
between them, which is why both are believed).

It is not the one to ship. Measured on the full set it reaches 39.9 against 41.6 for the external
direction, with its best scale at 8 rather than 7; on the hard subset its peak is 11.0 against 11.3.
It earns its place as a *component*: the adopted direction is the bisector of it and the external
one, which beats both on the subsets where they disagree.

The remaining survey checkpoints would not change this. The tool
(`dir-steering/tools/weight_diff_direction.py`) and the vector stay.
