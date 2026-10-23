# Spec Delta

## Purpose

Recover a refusal/steering direction from the weight difference between a public
abliterated checkpoint and our base weights — a weight-space derivation distinct from
the activation-contrast method — and report its geometry against, and (user-run) axis-A
efficacy beside, the accepted activation-derived `402` direction.

## ADDED Requirements

### Requirement: Comparable-quantization weight-diff
The weight-diff SHALL compare an abliterated checkpoint against our base weights only at
the same quantization, so each per-tensor difference is the abliteration edit and not a
requantization artefact. A base-match sanity check SHALL gate trust in the result: at
least one tensor the abliteration does not edit MUST diff to approximately zero, and the
derivation SHALL publish no direction when that check fails.

#### Scenario: Quantization mismatch refused
- **WHEN** the abliterated file and the base differ in quantization
- **THEN** the diff is reported as not comparable and no direction is published

#### Scenario: Base-match sanity check
- **WHEN** a tensor the abliteration does not edit differs materially from the base
- **THEN** the run records the difference as untrusted and emits no direction file

### Requirement: Per-layer rank-one direction recovery
At each residual-writing site the abliteration edit `ΔW = W_base − W_abliterated` SHALL
be treated as approximately rank-one along the removed direction, and the left singular
vector of `ΔW` SHALL be recovered per layer as a unit-norm f32 direction in the existing
direction format. The derivation SHALL record each layer's leading singular-value share
and SHALL mark any layer whose edit is not dominantly rank-one as low-confidence rather
than trust it silently.

#### Scenario: Rank-one layer recovered
- **WHEN** a layer's `ΔW` is dominated by its first singular value
- **THEN** its left singular vector is emitted as that layer's direction with the
  singular-value share recorded

#### Scenario: Non-rank-one layer flagged
- **WHEN** a layer's `ΔW` is not dominantly rank-one
- **THEN** that layer is flagged low-confidence instead of being emitted as a trusted direction

#### Scenario: Offline derivation
- **WHEN** the direction is derived
- **THEN** it is computed from the stored weights alone, launching no model and generating no text

### Requirement: Geometry report against the activation-derived vector
The recovered direction SHALL be reported geometrically against the `402` msuiche vector —
per-layer cosine, which layers carry a nonzero edit, and the recovered rank — as evidence
of what the abliteration targeted. Geometry SHALL be presented as evidence of alignment or
divergence only, never as proof of steering efficacy.

#### Scenario: Alignment reported, not efficacy
- **WHEN** the geometry report is produced
- **THEN** it states per-layer cosine and the edited-layer map and explicitly makes no efficacy claim

### Requirement: Evaluation is user-run axis-A against the msuiche baseline
A recovered candidate SHALL be evaluated only through the `402` axis-A harness at a
finishing token cap, against the msuiche baseline, and that evaluation SHALL stay user-run.
A candidate that is malformed, not comparable, or no better than msuiche SHALL be recorded
as a valid completed result, and this change SHALL adopt no runtime default direction.

#### Scenario: No autonomous default
- **WHEN** a candidate is recovered
- **THEN** this change records its geometry and user-run axis-A result without changing the
  default runtime direction

#### Scenario: A negative result is valid
- **WHEN** the candidate is no better than msuiche on axis-A
- **THEN** the outcome is recorded as a completed comparison, not a failure to retry

### Requirement: Domain variant survey is analysis only
The domain variant (`drowzeys` cybersecurity) SHALL be surveyed for an additional or
domain-specific edited direction as an analysis task, reporting its edited-layer map and
its geometry against the general recovered direction, with no commitment to adopt it.

#### Scenario: Survey without adoption
- **WHEN** the domain variant is surveyed
- **THEN** its edited-site map and geometry are recorded and no runtime change follows from the survey alone
