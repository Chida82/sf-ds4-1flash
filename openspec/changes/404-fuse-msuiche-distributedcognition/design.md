# Design

## Context

- **Two sources, one basis.** Both directions are HC-collapsed single-5120 residual
  directions for the same checkpoint. msuiche sits at the post-layer fold (`401`'s
  `residual_stream_post_layer`); distributedcognition's `refusal_directions.pt` sits
  at the layer input (`attn_norm` input). Same residual stream, one sub-layer apart.
- **`.pt` is directions, not weights.** distributedcognition ships both the full
  abliterated model and the measured per-layer directions. This change reads the
  directions and ignores the `wo_b`/`shared_experts.w2` weight edits — the runtime is
  projective (`401`), not a weight patch.
- **The `.pt` is a rich dict (verified).** Keys: `directions` plus per-layer `snr`,
  `cos_sim`, `composite`, `quality`, `n_layers`, `thinking_mode`="chat". Load it with
  torch in a disposable `/tmp` venv (torch is not installed system-wide; no global
  install) and read `directions`; the quality fields feed `405`'s per-layer gating.
- **Layer ranges differ (verified).** msuiche covers L1-39; distributedcognition's
  abliteration `target_range` is L4-36 (`abliteration_config.json`), edits on
  `attn.wo_b` + `ffn.shared_experts.w2`. Fusion overlaps on L4-36; on L1-3 and L37-39
  only msuiche has a direction.
- **Site cosine warning (FUSION §3).** A low per-layer cosine between the two can mean
  "different site", not "different concept". The depth offset must be handled before
  reading the cosine as redundancy vs complementarity.
- **Fusion algebra (FUSION §4).** Sign-align, unit-norm, per-layer cosine; high →
  denoise `normalize(a+b)`; low → subspace via SVD, top-k basis. Orthogonal-residual
  test: `r = a - (a·b)b`; keep the second basis only if ablating `r` measurably lowers
  refusal on a held-out harmful set.

## Goals / Non-Goals

**Goals:**
- Candidate fused vectors that `402` can rank against msuiche-alone.
- An offset-aware, measurement-gated fusion, not a blind sum.

**Non-Goals:**
- The runtime site (`401`) and dose schedule (`403`).
- The measurement harness (`402`).
- Reproducing distributedcognition's weight-edit abliteration.

## Decisions

### D1. Fuse into one residual vector, by default
- **Choice.** Re-express distributedcognition's layer-input direction at the fold
  depth (offset search) and fuse into one `.f32` applied at `401`'s residual hook.
- **Rejected.** Two separate hooks (each direction at its own site) doubles the
  runtime edit and the dose search; kept only as a fallback if the cosine stays low
  after the offset, which would mean the two are genuinely complementary.

### D2. Denoise vs subspace by cosine, after the offset
- High cosine → the two agree → `normalize(a+b)` (denoise, rank 1). Low cosine →
  subspace basis k=1,2,3. The orthogonal-residual test decides whether
  distributedcognition's component survives; a failing residual means drop it and ship
  msuiche-alone.

### D3. Offset search, not assumed alignment
- Try layer offsets in {-1, 0, +1}: distributedcognition's layer L input is near
  msuiche's layer L-1 output. The offset that maximizes the median per-layer cosine is
  used; report it in the sidecar.

### D4. Pure-algebra tool, self-checked
- `fuse_directions.py` is vector algebra over 40×5120 arrays: a `__main__` assert
  self-check on tiny fixtures (sign-align, denoise norm, SVD basis shape). No model,
  no framework, no new dependency.

### D5. Measurement is the gate, the knee is the target
- Every candidate goes through `402`. Keep the candidate that beats msuiche-alone on A
  with B/C/D unmoved; prefer the lowest rank that achieves it (collateral rises with
  rank). No candidate is kept on cosine alone.

### D6. Partial overlap: msuiche-alone outside L4-36
- **Choice.** Fuse only where both have a direction (L4-36). On L1-3 and L37-39 keep
  msuiche's direction unchanged; the sidecar records the per-layer source. Weight the
  fusion by distributedcognition's published per-layer `composite`/`snr` where it
  helps, gated by `402`.
- **Rejected.** Extrapolating distributedcognition past its measured range, or zeroing
  msuiche on L1-3/L37-39 to match the shorter range — both discard signal one source
  actually has.

## Risks / Trade-offs

- **[Low cosine is site, not concept]** → the offset search and the orthogonal-residual
  test separate the two before any denoise/subspace choice.
- **[Over-rank adds collateral]** → k is searched 1→3 and gated by `402`'s B/C/D, not
  maximized.
- **[Gated `.pt`]** → needs the user's `HF_TOKEN` and the Responsible Use Agreement on
  the distributedcognition repo; the tool's self-check runs on fixtures without it.
- **[Non-monotone alpha inherited]** → the fused vector's dose is still set at `401`/
  `403`; 0.5 is msuiche's knee and higher regresses. The sidecar carries the caveat.
