# Spec Delta

## ADDED Requirements

### Requirement: Every layer's readout comes from one full-depth pass
With `DS4_V41_LENS_FILE` set, on the last prompt token of a sync that runs
token by token, the engine SHALL record, at the top of each layer L ≥ 1, the
logits of the tokens listed in `DS4_V41_LENS_IDS` and the vocabulary
log-sum-exp of a model stopped after layer L−1.

#### Scenario: The probe does not disturb the token
- **WHEN** the same decision runs with and without the variables
- **THEN** its final option logits are bitwise equal

#### Scenario: Unset is unchanged
- **WHEN** the variables are not set
- **THEN** decode logits are bitwise those of the build before this change

#### Scenario: It equals a truncated run
- **WHEN** the lens row at L and a run stopped at L by `870`'s probe use the same schedule
- **THEN** their option logits are bitwise equal

### Requirement: Depth and contrast are kept only if they beat what exists
The record SHALL state whether decision depth predicts disagreement with the
thinking answer better than confidence, and whether a layer contrast improves
held-out accuracy or NLL.

#### Scenario: Recorded verdicts
- **WHEN** the analysis finishes
- **THEN** the record holds the per-layer table and the three verdicts
