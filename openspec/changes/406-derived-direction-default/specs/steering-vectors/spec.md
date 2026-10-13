# Spec Delta

## Purpose

Select and bundle a default steering direction only from a measured `402`
acceptance, with provenance tracing the shipped vector to the run that chose it,
and never turning steering on by default.

## ADDED Requirements

### Requirement: Measurement-gated default direction selection
The child SHALL designate a default recommended steering direction only from an
identified `402` acceptance run in which a candidate beat the named single-source
baseline without failing the quality guards. The selection SHALL record the
candidate's vector hash, source/application identity, scale and the accepting run
id. A hand-picked file without an accepting run SHALL NOT become the default.

#### Scenario: No candidate wins
- **WHEN** no `404`/`405` candidate beats the single-source baseline through `402`
  with the guards preserved
- **THEN** no default is shipped, the single-source reference stays named, and the
  negative result is recorded

#### Scenario: A later candidate supersedes the default
- **WHEN** a new candidate is accepted by a later `402` run
- **THEN** the default selection is re-recorded from that run's identity rather
  than edited in place, and the superseded provenance remains traceable

### Requirement: Default provenance and opt-in preserved
A bundled default direction SHALL carry a provenance sidecar naming its source,
derivation or fusion method, accepting `402` run id and scale, and the docs SHALL
name the vector and scale to pass. Shipping a default SHALL NOT enable steering by
default, weaken the opt-in refusal, or change the disabled-steering inference path
or the parity gate.

#### Scenario: Default present but steering still refused
- **WHEN** the child ships a recommended default direction
- **THEN** a run without the steering opt-in still refuses steering exactly as
  before, and the default is applied only when the operator passes it explicitly

#### Scenario: Provenance names the accepting run
- **WHEN** an operator inspects the bundled default
- **THEN** its sidecar identifies the candidate, its method and the `402` run that
  accepted it, so the shipped bytes trace to a measurement
