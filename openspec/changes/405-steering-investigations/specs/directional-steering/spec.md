# Spec Delta

## ADDED Requirements

### Requirement: Per-layer steering scale
An optional per-layer scale file SHALL multiply the steering scale per layer, so that
layers may be attenuated or zeroed (those below the derivation null gate). With no
per-layer file, a flat scale SHALL apply and output SHALL stay bitwise identical to a
build without this change.

#### Scenario: Masked layers are skipped
- **WHEN** a per-layer scale with layer 3 set to 0 is loaded
- **THEN** the steering edit at layer 3 is a no-op and other layers are unchanged

#### Scenario: No-op gate
- **WHEN** no per-layer scale file is given
- **THEN** the 65-token decode logits, KV and Engram are bitwise identical to a run
  without this change

### Requirement: Event-based scale decay
An opt-in event-decay mode SHALL lower the steering scale when `dot(d[L], y)` returns
to the comply range, clamped non-increasing within a phase, falling back to the fixed
schedule of `403` on a noisy projection. With the mode off, output SHALL stay bitwise
identical.

#### Scenario: Scale drops after the decision
- **WHEN** event decay is on and the projection returns to the comply range mid-answer
- **THEN** the applied scale is at or below its value at the prior token

#### Scenario: No-op gate
- **WHEN** event decay is off
- **THEN** output matches the fixed-schedule run bitwise

### Requirement: Steering projection log
A diagnostic env SHALL print `dot(d[L], y)` per layer per token without altering the
activation. Output SHALL be bitwise identical whether the env is set or not.

#### Scenario: Log does not change output
- **WHEN** the projection-log env is set on a steered run
- **THEN** the decode logits, KV and Engram are bitwise identical to the same run with
  the env unset
