# Spec Delta

## ADDED Requirements

### Requirement: Second residual direction
The V4.1 residual site SHALL accept an optional second per-layer unit direction
(`--dir-steering-file-2`) with its own constant scale (`--dir-steering-residual-2`),
applied as a second in-place weighted fold after the first on every route that applies
the first (token-major decode, prefill batch, decoder suffix). The second direction
SHALL be subject to the same opt-in gate, the same disable switch and the same
persistence refusal as the first, and SHALL be validated by the same loader rules
(shape, zero anchor row, unit rows).

#### Scenario: Second file without the opt-in
- **WHEN** `--dir-steering-file-2` is given and neither `--allow-v41-steering` nor
  `DS4_ALLOW_V41_STEERING` admits steering
- **THEN** the engine refuses to start with the same message as for the first direction

#### Scenario: Zero second scale is the single-direction run
- **WHEN** a second file is given with `--dir-steering-residual-2 0`
- **THEN** the second direction is not loaded and logits, Engram history and KV state
  are bitwise identical to the run with the first direction alone

#### Scenario: Scale without a file
- **WHEN** `--dir-steering-residual-2` is nonzero and no second file is given
- **THEN** the engine refuses to start naming the missing file

### Requirement: Composition of two folds is stated honestly
Two sequential folds SHALL be documented as sequential removals. The run identity
SHALL record the per-layer cosine between the two loaded directions, and the term
"rank-2 span removal" SHALL be used only for pairs whose median absolute cosine is
below the documented orthogonality threshold. The runtime SHALL NOT refuse a
non-orthogonal pair.

#### Scenario: Orthogonal pair nulls both projections
- **WHEN** the two directions are orthogonal per layer and both scales are 1
- **THEN** after the two folds the projections of the activation onto both directions
  are zero within tolerance, independent of fold order

#### Scenario: Non-orthogonal pair is recorded, not refused
- **WHEN** the two directions have median absolute cosine above the threshold
- **THEN** the run proceeds, the identity records the cosine, and the report describes
  the arm as two sequential folds

### Requirement: Rank-2 run identity
A run with a second direction SHALL carry a `rank2` record (second file hash, second
scale, per-layer cosine to the first) inside its intervention identity, so that it is
never cached, compared or reported as a rank-1 run.

#### Scenario: Identity distinguishes rank-1 and rank-2
- **WHEN** two runs differ only in the presence of a second direction
- **THEN** their intervention identities differ and the harness treats them as distinct arms

### Requirement: Bounded fold activation capture
When `DS4_V41_DUMP_STEER_INPUT=<path>` is set, the engine SHALL append the pre-edit
fold input of row 0 (one row of `DS4_N_EMBD` f32 per model layer) to that path on every
route that applies the fold, reading the tensor only after synchronising the device and
resuming command recording afterwards. The capture SHALL leave the generated output
unchanged. When the variable is unset, the fold SHALL perform no capture-related
allocation or dispatch. The switch SHALL be classified `probe` and SHALL be reported at
engine open like every out-of-normal switch.

#### Scenario: Capture does not change output
- **WHEN** the same prompt is generated with and without the capture variable set
- **THEN** the generated tokens are identical and the capture file holds `tokens × layers`
  rows

#### Scenario: Unset capture is free
- **WHEN** the variable is unset
- **THEN** the fold performs no readback, allocation or dispatch for capture and the
  engine prints no `probe` line for it at open

### Requirement: Activation-contrast extraction records provenance
A direction derived from captures SHALL be written as a per-layer unit f32 with a
sidecar naming the method, the site, the prompt classes and counts, the per-layer raw
difference norms and the hash of the written bytes. A derived direction SHALL be treated
as a `402` candidate, never as an accepted vector.

#### Scenario: Derived direction is a candidate
- **WHEN** the extractor writes a direction
- **THEN** its sidecar carries the provenance fields and the direction is evaluated
  through the acceptance harness before any claim about it is recorded
