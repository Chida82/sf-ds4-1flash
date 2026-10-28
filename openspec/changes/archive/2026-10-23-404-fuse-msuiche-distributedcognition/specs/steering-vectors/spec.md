# Spec Delta

## Purpose

Produce validated, interpretable steering-vector candidates and compare fusion with its single-source alternatives without overstating source-site equivalence.

## ADDED Requirements

### Requirement: Validated direction sources
Fusion SHALL validate source identity/layout, finite row values, shape and declared masks before extraction or algebra. A serialized tensor SHALL NOT be identified solely by a matching storage byte count. Unsupported inputs SHALL fail without publishing partial candidates or executing arbitrary serialized code.

#### Scenario: Same storage size with another layout
- **WHEN** an input has the expected storage length but an unverified tensor key, stride, offset or dtype
- **THEN** extraction rejects it rather than treating its bytes as the directions tensor

#### Scenario: Weight range differs from measured rows
- **WHEN** source weight edits cover fewer layers than the available measured directions
- **THEN** measured row availability and the chosen experimental mask are reported separately

### Requirement: Explicit geometric alignment
Fusion SHALL normalize and sign-align participating rows and report offset candidates, comparison mask, counts and cosines. Automatic offset selection SHALL use comparable valid support. A geometric winner SHALL NOT be represented as proof of runtime-hook correspondence or behavioral efficacy.

#### Scenario: Offset result
- **WHEN** +1 has the largest median cosine on the declared common mask
- **THEN** metadata records that geometric result without asserting that the runtime must shift its hook index

### Requirement: Distinct rank-one fusion candidate
The production denoise candidate SHALL contain one normalized sum of aligned unit directions per paired layer, retaining the anchor row where the other source is absent and preserving anchor masks. Equivalent denoise and rank-one SVD results SHALL NOT be emitted as independent candidates. Multi-direction subspaces SHALL NOT be represented as one direction per layer.

#### Scenario: Duplicate candidate removed
- **WHEN** aligned unit inputs make the leading SVD direction equal to denoise
- **THEN** only one production candidate represents that direction

### Requirement: Faithful orthogonal diagnostic
The orthogonal diagnostic SHALL record residual norms before normalization. Unpaired rows and residuals at or below the documented degeneracy threshold SHALL remain zero, not fall back to an original direction. Nonzero rows SHALL represent the normalized component of the second source orthogonal to the first.

#### Scenario: Identical sources
- **WHEN** paired source directions are identical after sign alignment
- **THEN** the orthogonal diagnostic row and its recorded residual norm are zero

### Requirement: Candidate provenance and shape
Each candidate SHALL carry source hashes/layout identities, source hooks, application hook/revision, masks, offset, per-layer diagnostics and output hash/shape. Outputs SHALL follow the 40x5120 f32 contract. Regeneration SHALL NOT silently delete old user outputs or count stale files as new candidates.

#### Scenario: Regenerated candidates
- **WHEN** corrected candidates are generated in a fresh output directory
- **THEN** the report identifies their new hashes and does not include a stale duplicate from an older run

### Requirement: Measurement-gated fusion selection
Fusion SHALL be compared with both single-source local interventions using the same declared application site, comparable tuning budgets and separate holdout data. It SHALL be retained only on the predeclared benefit with non-inferior quality guards. A negative or inconclusive result SHALL preserve the best supported single-source choice rather than force a fusion winner.

#### Scenario: Fusion does not beat the stronger source
- **WHEN** fusion beats one single source but does not establish benefit over the stronger comparator
- **THEN** fusion is not accepted and the measured result is recorded

### Requirement: Model-less algebra checks
The tool SHALL have runnable offline checks for extraction validation, unequal input norms, sign alignment, masks, exact shape and degenerate orthogonal rows. A check SHALL fail when its asserted property is false; unconditional-success assertions SHALL NOT count as coverage.

#### Scenario: Tiny residual and nonfinite input
- **WHEN** near-identical unit rows or nonfinite inputs are tested
- **THEN** the former follow the documented zero-residual rule and the latter are rejected
