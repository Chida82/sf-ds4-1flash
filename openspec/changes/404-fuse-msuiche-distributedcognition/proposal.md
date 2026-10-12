# Proposal

## Why

Two V4.1 refusal directions exist for the same base model
(`deepseek-ai/DeepSeek-V4.1-Flash` rev `fb2764a5`, hidden 5120), and both are
single-stream HC-collapsed residual directions:

- **msuiche**: the `.f32` from `401`'s converter, measured and applied at the
  post-layer fold (`residual_stream_post_layer`, `401`'s site), alpha knee 0.5.
- **distributedcognition**: `refusal_directions.pt`, per-layer directions measured at
  the HC-collapsed residual stream (`attn_norm` input, i.e. the layer input), 128
  harmful vs 128 harmless, orthogonalized against the harmless mean.

They differ only in depth (layer-input vs post-layer-output of the same residual
stream), so a per-layer fusion is well-posed, and the owner wants a broad removal.
Fusing them (FUSION §4) can beat either alone — but only if measured, so this change
produces candidate vectors and `402` judges them. It is the "modify the vector" step
and runs after `402`.

## What Changes

- **Fusion tool.** `dir-steering/tools/fuse_directions.py`: reads msuiche's `.f32` and
  distributedcognition's `.pt`, sign-aligns and unit-norms each per-layer pair, scans
  a small layer offset (the two sites are one sub-layer apart), and emits fused `.f32`
  candidates — `denoise` (`normalize(a+b)` where the per-layer cosine is high) and
  `subspace` k=1,2,3 (SVD basis where it is low) — each with a `.json` sidecar
  (method, k, offset, sources, provenance).
- **Selection by measurement.** Each candidate is a drop-in for `401`'s residual hook;
  `402` scores it. A candidate is kept only if it beats msuiche-alone on axis A
  without worsening B/C/D. Rank k is searched, not maximized (more rank removes more
  but adds collateral).
- **Directions, not weights.** The `.pt` holds residual directions; this change uses
  them directly, not distributedcognition's `wo_b`/`shared_experts.w2` weight edits.
- **No runtime change.** Application is `401` (site) and `403` (dose); this change is
  tooling only.

## Capabilities

### New Capabilities
- `steering-vectors`: offline tooling that derives, converts and fuses V4.1 steering
  direction files, judged by `402`.

## Impact

- `dir-steering/tools/fuse_directions.py` (new): pure vector algebra, a `__main__`
  assert self-check, no model and no new dependency beyond what the repo already uses.
- `dir-steering/README.md`: the fusion workflow and the candidate naming.
- `docs/upstream-prs.md` / registry: provenance (msuiche GLP-39; distributedcognition
  grimjim norm-preserving biprojected abliteration); not in source comments.
- Depends on `401` (converter + residual site) and `402` (to judge). Benefits from
  `403` (tunable dose). No `ds4.c` change.
