# steering-vectors Specification

## Purpose
Select and bundle a default steering configuration only from a measured
acceptance on the 44-id set (`com-steering/kpi.md`), with provenance tracing the
shipped bytes to the runs that chose them, and never turning steering on by
default.

## Requirements

### Requirement: Measurement-gated default selection
The child SHALL designate a default steering configuration only from identified
acceptance runs on the 44-id set (`com-steering/kpi.md`) in which it beat the named
single-source baseline. A hand-picked file without an accepting run SHALL NOT
become the default.

#### Scenario: Selection records the accepting runs
- **WHEN** a configuration is designated the default
- **THEN** the selection records its slot vectors and hashes, scales, phase gates
  and the accepting run ids from `com-steering/result.md`, in both reasoning phases

#### Scenario: No candidate wins
- **WHEN** no candidate beats the single-source baseline on the 44-id set with the
  guards preserved
- **THEN** no default is shipped, the single-source reference stays named, and the
  negative result is recorded

#### Scenario: A later candidate supersedes the default
- **WHEN** a new configuration is accepted by a later 44-id run
- **THEN** the default selection is re-recorded from that run's identity rather
  than edited in place, and the superseded provenance remains traceable

### Requirement: Default provenance and opt-in preserved
A bundled default SHALL carry a provenance sidecar naming its slot vectors and
their derivation or fusion method, the accepting run ids and the scales, and the
docs SHALL name the profile and how it is passed. Shipping a default SHALL NOT
enable steering by default, make a run steer without a profile being passed, or change the
disabled-steering inference path or the parity gate.

#### Scenario: Default present but steering still refused
- **WHEN** the child ships a recommended default configuration
- **THEN** a run that passes no profile computes exactly as before, unsteered, and the default is applied only when the operator passes it explicitly

#### Scenario: Provenance names the accepting run
- **WHEN** an operator inspects the bundled default
- **THEN** its sidecar identifies the configuration, its slot methods and the runs
  that accepted it, so the shipped bytes trace to a measurement
