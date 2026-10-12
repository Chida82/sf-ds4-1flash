# Tasks

Depends on `401` (converter + residual site) and `402` (to judge). Prerequisite for
real data: the user sets `HF_TOKEN` and accepts the Responsible Use Agreement on the
distributedcognition repo; `refusal_directions.pt` and msuiche's GGUF download to
`/tmp`. The tool's self-check (1.3) needs neither.

## 1. Ingest and align

- [ ] 1.1 `dir-steering/tools/fuse_directions.py`: load msuiche's `.f32` (40×5120, via
  `401`) and distributedcognition's `refusal_directions.pt` (per-layer 5120). Map both
  to a 40×5120 array, sign-align each per-layer pair (project onto a common reference)
  and unit-norm. Verify the loaded shapes and that layer 0 (no msuiche direction) is
  handled.
- [ ] 1.2 Offset search over {-1,0,+1}: pick the offset maximizing the median per-layer
  cosine; record it. Verify the chosen offset and the per-layer cosine vector are in
  the sidecar.
- [ ] 1.3 `__main__` assert self-check on tiny fixtures: sign-align flips a negated
  pair, denoise is unit-norm, the SVD basis has the right shape. Verify
  `python3 dir-steering/tools/fuse_directions.py --self-check` exits 0.

## 2. Fuse candidates

- [ ] 2.1 Emit `denoise` (`normalize(a+b)` per layer) and `subspace` k=1,2,3 (SVD
  basis) candidates, each a `.f32` + `.json` sidecar (method, k, offset, sources,
  provenance). Verify each `.f32` is 819200 bytes and loads under `401`'s runtime.
- [ ] 2.2 Orthogonal-residual test per layer (`r = a-(a·b)b`): emit the residual-only
  vector as a diagnostic candidate. Verify the sidecar records whether `r` has
  non-trivial norm per layer.

## 3. Measure and pick

- [ ] 3.1 Run each candidate through `402` against the msuiche-alone baseline (A, B, C,
  D, and the breadth map). Verify the report ranks them and flags any that worsen
  B/C/D. Model runs share the lock; serialize.
- [ ] 3.2 Keep the lowest-rank candidate that beats msuiche-alone on A with B/C/D
  unmoved; if none does, keep msuiche-alone and record the null result. Verify the
  chosen vector's sidecar names the winning method/k/offset and the `402` numbers.

## 4. Docs

- [ ] 4.1 `dir-steering/README.md`: the fusion workflow, candidate naming, and that
  the `.pt` directions are used projectively, not as weight edits. Verify no doc claims
  a fused vector is validated before `402` has scored it.
- [ ] 4.2 Provenance in `docs/upstream-prs.md`/registry (msuiche GLP-39;
  distributedcognition grimjim method): not in source comments.

## 5. Integration

- [ ] 5.1 `make test`, parity on the disabled path token-identical,
  `openspec validate 404-fuse-msuiche-distributedcognition --strict`. No commit or push
  without a request.
