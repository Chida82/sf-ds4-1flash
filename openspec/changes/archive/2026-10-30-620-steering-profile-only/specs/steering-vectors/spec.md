# Spec Delta

## MODIFIED Requirements

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
