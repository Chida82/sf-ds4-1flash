# Design

## Context

- The steering edit (`401`) is `y -= scale * d[L] * dot(d[L], y)` on the post-HC-fold
  residual, layers 1-39. `dot(d[L], y)` — the model's current alignment with the
  refusal direction — is already computed every token, so reading it costs nothing.
- msuiche's card gives the per-layer picture: the mean dose at alpha 1 is 3% of the
  residual norm at L1 and 41% at L30; layers 1-6 sit below the derivation null gate
  (shipped, but the first to break at high alpha). So a flat scale over all layers is
  not optimal: the signal is concentrated.
- The response is non-monotone (0.5 knee, 1.0 code-switches, 2.0 regresses), so the
  place the output breaks is worth mapping once rather than re-deriving per run.
- Every item here is judged by `402`; it is not a perf change, so the gate is axis A
  up with B/C/D flat, under the config's CI rule.

## Goals / Non-Goals

**Goals:**
- Cheaper collateral (per-layer scale), a smarter fade (event decay), and visibility
  (projection log).
- Two findings that guide tuning without new code (generalization, breaking point).

**Non-Goals:**
- A new vector or fusion (`404`), the base residual hook (`401`), the fixed decay
  (`403`). This change only refines and measures them.

## Decisions

### D1. Per-layer scale by measured separation
- A per-layer scale vector multiplies the base scale. Set it from the measured
  good-vs-bad separation of `dot(d[L], y)`, zeroing layers below the null gate.
- **Start from a published prior.** distributedcognition's `refusal_directions.pt`
  already carries per-layer `snr`, `cos_sim` and `composite` (verified on download):
  use them as the initial layer weighting and confirm against a fresh separation pass,
  rather than deriving blind.
- **Rejected:** a single global scale — it over-steers the weak early layers and
  wastes collateral budget there for no refusal removal.

### D2. Event decay as a guarded mode, not a replacement
- An opt-in mode that lowers the scale when `dot(d[L], y)` returns to the comply
  range, instead of `403`'s token count. Kept only if `402` shows it beats the fixed
  schedule on the typical mix.
- **Rejected:** replacing `403`'s schedule outright — the fixed schedule is
  predictable and already measured; event decay is adaptive but can oscillate.

### D3. Projection log is read-only
- The diagnostic prints `dot(d[L], y)` and never alters the activation, so output
  stays bitwise identical whether or not it is on. It is a `probe` env, not a flag.

### D4. Generalization and breaking point are findings, not code
- Both are produced by running `402` across domains and across a scale/decay grid and
  recording the result in `perf-record.md`/the registry. No runtime change.

### D5. Attention second channel is conditional
- Tried as residual-small + attn-tiny vs residual alone. It ships a knob only if `402`
  shows a win; otherwise it is recorded as a dropped idea. Steering on attention is
  noted fragile upstream.

## Risks / Trade-offs

- **[Per-layer scale overfits the measurement set]** -> derive the mask on one harmful
  set, confirm on a held-out one via `402` before shipping it.
- **[Event decay oscillates]** -> clamp to monotone non-increasing within a phase and
  fall back to `403`'s schedule if the projection is noisy; keep it opt-in.
- **[Projection log slows decode]** -> it only reads a scalar already computed and
  prints off the hot path; verify decode tokens/s is unchanged with it off and within
  noise with it on.
- **[Findings read as guarantees]** -> record n and the resolution; the n=32 suites
  resolve ~30 points, so a map is a guide, not a contract.
