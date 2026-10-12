# Tasks

Depends on `401` (converter + residual site) and `402` (to judge). Prerequisite for
real data: the user sets `HF_TOKEN` and accepts the Responsible Use Agreement on the
distributedcognition repo; `refusal_directions.pt` and msuiche's GGUF download to
`/tmp`. The tool's self-check (1.3) needs neither.

Status 2026-10-13: `dir-steering/tools/fuse_directions.py` authored (offline
self-check green); run on the real msuiche `.f32` (from `401`'s converter) and
distcog `refusal_directions.pt` (read without torch). Empirical offset = **+1**
(median per-layer cosine -1 -> 0.579, 0 -> 0.688, +1 -> 0.779), confirming the two
sites are one sub-layer apart. Candidates written (3 x 819200 B) to /tmp, not
committed (binaries derived from gated sources; regenerable). Group 3 (measure/pick)
needs `401`'s hook + `402` model runs -> deferred.

## 1. Ingest and align

- [x] 1.1 `dir-steering/tools/fuse_directions.py`: loads msuiche's `.f32` (40x5120)
  and distcog's `refusal_directions.pt` (zip `data/0` storage read as raw f32, no
  pickle executed); maps both to 40x5120, sign-aligns each per-layer pair, unit-norms;
  layer 0 (no direction) handled. Shapes verified on the real artifacts.
- [x] 1.2 Offset search over {-1,0,+1}: picks the offset maximizing the median
  per-layer cosine (chosen +1 on the real data); offset and the per-layer cosine
  vector are in each sidecar.
- [x] 1.3 `__main__` assert self-check on tiny fixtures: sign-align flips a negated
  pair, denoise is unit-norm, the SVD basis is orthonormal/right shape.
  `python3 dir-steering/tools/fuse_directions.py --self-check` exits 0.

## 2. Fuse candidates

- [x] 2.1 Emits `denoise` (`unit(a+b)`) and `subspace_k1` (top SVD right-singular
  vector; == denoise for unit inputs) as single-direction `.f32` (819200 B) + `.json`
  sidecars (method, offset, per-layer cosine, sources, provenance). DEVIATION: k=2,3
  are NOT single-direction files -- `401`'s runtime applies one direction per layer,
  so genuine rank-k>1 removal needs a multi-direction runtime extension (tracked in
  `405`); the SVD basis is still computed for analysis. "loads under 401's runtime" is
  *model-backed* once `401`'s hook lands.
- [x] 2.2 Orthogonal-residual test per layer (`r = b-(a.b)a`): emitted as the
  `ortho` diagnostic candidate; the sidecar records per-layer residual norms.

## 3. Measure and pick

- [ ] 3.1 Run each candidate through `402` against the msuiche-alone baseline (A, B,
  C, D, breadth). *model-backed* (needs `401`'s hook + `402` runs); the harness and
  candidates are ready. Model runs share the lock; serialize.
- [ ] 3.2 Keep the lowest-rank candidate that beats msuiche-alone on A with B/C/D
  unmoved; else keep msuiche-alone and record the null result. *model-backed*.

## 4. Docs

- [x] 4.1 `dir-steering/README.md`: the fusion workflow, candidate naming, directions
  used projectively (not weight edits), and that a fused vector is not validated until
  `402` scores it.
- [x] 4.2 Provenance in `docs/upstream-prs.md` (msuiche GLP-39; distributedcognition
  grimjim norm-preserving biprojected abliteration) with the +1 offset finding; not in
  source comments.

## 5. Integration

- [x] 5.1 `openspec validate 404-fuse-msuiche-distributedcognition --strict` passes.
  `make test` is unaffected and not re-run: this change adds only a standalone python
  tool (imported by nothing) plus `.md` docs -- no C, env, Makefile `test:` target or
  runtime change (make test was green at `402`). Parity on the disabled path is
  unchanged (tooling only, no `ds4.c` change); *model-backed* parity re-run not needed.
  Standing commit authority on `sf/steering` for this steering work.
