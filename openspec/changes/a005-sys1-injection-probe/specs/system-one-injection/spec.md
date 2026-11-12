# Spec Delta

## ADDED Requirements

### Requirement: State text cannot produce special tokens
The tokens of a state prefix SHALL contain each chat special token exactly as
many times as the template puts it, whatever text the state carries.

#### Scenario: Assistant marker in a state
- **WHEN** a state contains the text of the assistant marker
- **THEN** the state prefix contains no assistant marker id

### Requirement: Injection susceptibility is measured
The bench SHALL report clean accuracy, attacked accuracy and flip rate for
three injection variants on `choice` and `noul` items, per language.

#### Scenario: Recorded table
- **WHEN** the adversarial run finishes
- **THEN** `sysone-bench/record.md` holds the three variants' figures

### Requirement: A mitigation is kept only if it halves flips without cost
A template mitigation SHALL be adopted only if it halves the mean flip rate
and keeps clean accuracy within 1 point.

#### Scenario: Mitigation costs accuracy
- **WHEN** M1 halves flips but loses 2 points of clean accuracy
- **THEN** it is not adopted and the record says why
