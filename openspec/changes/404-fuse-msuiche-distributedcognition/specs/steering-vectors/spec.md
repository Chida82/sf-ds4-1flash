# Spec Delta

## ADDED Requirements

### Requirement: Direction fusion tool
`dir-steering/tools/fuse_directions.py` SHALL fuse msuiche's `.f32` and
distributedcognition's `refusal_directions.pt` into 40×5120 candidate steering files.
It SHALL sign-align and unit-norm each per-layer pair, choose the layer offset in
{-1,0,+1} that maximizes the median per-layer cosine, and emit `denoise` and
`subspace` (k=1,2,3) candidates, each with a `.json` sidecar recording method, k,
offset, sources and provenance. A `--self-check` run SHALL pass with no model.

#### Scenario: Offset chosen and recorded
- **WHEN** the two sources are fused
- **THEN** the sidecar records the selected offset and the per-layer cosine vector,
  and each candidate `.f32` is 819200 bytes

#### Scenario: Self-check without data
- **WHEN** `fuse_directions.py --self-check` runs with no vectors present
- **THEN** it exercises sign-align, denoise norm and the SVD basis on fixtures and
  exits 0

### Requirement: Measurement-gated selection
A fused candidate SHALL be accepted only when `402` shows it beats the msuiche-alone
baseline on axis A without worsening axes B, C or D. The lowest-rank candidate that
clears that bar SHALL be chosen; when none does, msuiche-alone SHALL be kept and the
null result recorded. No candidate SHALL be accepted on cosine alone.

#### Scenario: Candidate kept
- **WHEN** `subspace` k=1 lowers refusal on axis A with B/C/D unchanged, and k=2,3 add
  only collateral
- **THEN** k=1 is chosen and its sidecar records the `402` numbers

#### Scenario: No improvement
- **WHEN** no fused candidate beats msuiche-alone on A without moving B/C/D
- **THEN** msuiche-alone is kept and the null result is recorded
