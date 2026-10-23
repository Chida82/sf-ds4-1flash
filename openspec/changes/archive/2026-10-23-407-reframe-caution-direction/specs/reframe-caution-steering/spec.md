# Spec Delta

## Purpose

Derive, validate, compose and evaluate a second steering direction that targets the
model's reframe/caution behaviour on harmful prompts — the substantive-but-reframed
answer that remains after the refusal is removed — as an intervention separate from,
and separately measured against, the refusal direction.

## ADDED Requirements

### Requirement: Contrast-pair derivation at the live site
The reframe/caution direction SHALL be derived at the live residual site
(`v41_attn_input_weighted_fold_post_engram`) on reframed-versus-direct contrast pairs of
the same prompt, not on refusal-versus-compliance pairs. The candidate SHALL be a
validated per-layer unit-norm f32 direction file and SHALL fail without publishing a
partial candidate when a pair set or a layer is unusable.

#### Scenario: Behaviour axis of the pairs
- **WHEN** the derivation is given contrast pairs
- **THEN** it uses reframed-vs-direct responses as the two poles, and records the pair
  source and count in the candidate metadata, rather than reusing refusal-vs-compliance pairs

#### Scenario: Malformed candidate rejected
- **WHEN** a derived row is non-finite, off-norm, or a required layer is missing
- **THEN** the derivation reports the fault and emits no candidate file

### Requirement: Distinctness from the refusal direction
The reframe/caution candidate SHALL report its per-layer cosine against the accepted
refusal direction. A candidate near-collinear with the refusal direction on the common
layer mask SHALL be reported as not-distinct, which completes the question; a distinct
candidate SHALL be treated as targeting a separate behaviour and never as proof of
efficacy on its own.

#### Scenario: Near-collinear candidate
- **WHEN** the median per-layer cosine to the refusal direction is at or above the
  documented distinctness threshold
- **THEN** the candidate is recorded as not-distinct and no composition arm is run

#### Scenario: Distinct candidate
- **WHEN** the candidate is distinct from the refusal direction
- **THEN** distinctness is recorded as a precondition for the composition experiment,
  not as a behavioural result

### Requirement: Two-direction composition is a task-local experiment
Composition SHALL place the refusal vector on the decision and the reframe/caution
vector on the answer body by reusing the `403` schedule machinery, as an experimental
evaluation arm. It SHALL NOT add an always-on runtime path, and with the reframe scale
at zero it SHALL reduce exactly to the single-vector `401`/`403` behaviour, bitwise.

#### Scenario: Reframe scale zero
- **WHEN** the composition arm sets the reframe/caution scale to zero
- **THEN** the run is bitwise identical to the single refusal-vector run under the same schedule

#### Scenario: No always-on path
- **WHEN** the change is complete
- **THEN** the composition exists only as an evaluation arm, and the default runtime applies the refusal direction alone

### Requirement: Acceptance on finished answers at a fixed refusal rate
Efficacy SHALL be measured through the `402` axis-A harness at a token cap large enough
for answers to finish, comparing the composition arm against the single refusal-vector
arm while holding the refusal rate at the single-vector level. Acceptance SHALL require
DEFLECT to fall and COMPLY to rise within the declared benign over-refusal and KL
guards; otherwise the result SHALL be recorded as a completed negative.

#### Scenario: DEFLECT reduced within guards
- **WHEN** the composition lowers DEFLECT and raises COMPLY at an unchanged refusal rate
  and the benign over-refusal and KL guards hold
- **THEN** the reframe/caution direction is accepted for that site and schedule

#### Scenario: No benefit or benign cost
- **WHEN** the composition does not lower DEFLECT, or lowers it only by raising benign
  over-refusal or KL past the guard
- **THEN** the result is recorded as a completed negative and no runtime rank is added

#### Scenario: Truncated grading refused
- **WHEN** the token cap is small enough that answers do not finish
- **THEN** the acceptance is not reported, because the grade would read the intro rather
  than the delivered answer
