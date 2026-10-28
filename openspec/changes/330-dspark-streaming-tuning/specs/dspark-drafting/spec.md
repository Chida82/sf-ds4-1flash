# Spec Delta

## ADDED Requirements

### Requirement: Automatic cache budget leaves room for the drafter
When `--dspark` is given without an explicit expert-cache size, the automatic expert-cache budget SHALL be reduced by the drafter's resident size, and the startup budget line SHALL name that reduction. An explicit expert-cache size SHALL keep its current meaning.

#### Scenario: Automatic budget with the drafter
- **WHEN** the CLI starts with `--ssd-streaming --dspark --mtp-model FILE` and no expert-cache size
- **THEN** the admitted cache is the automatic budget without the drafter, minus the drafter's resident size, and the startup line says so

#### Scenario: Explicit size
- **WHEN** the CLI starts with `--dspark` and `--ssd-streaming-cache-experts 82GB`
- **THEN** the admitted cache is the same as without `--dspark`

### Requirement: Draft length by expected cost
When `--dspark-confidence` is not given, each cycle SHALL verify the k drafts, from zero to the block size, that maximise expected tokens over expected time. Expected tokens SHALL be one plus the sum of the running products of the per-position acceptance estimates. Expected time SHALL come from a verify-cost table measured on this machine and corrected from measured cycle times. A cycle with k zero SHALL be an ordinary decode step. The choice of k SHALL NOT change the generated tokens.

#### Scenario: Unconfident block
- **WHEN** every per-position acceptance estimate of a block is near zero
- **THEN** the cycle verifies no draft and decodes one token as without `--dspark`

#### Scenario: Greedy tokens unchanged across rules
- **WHEN** the same greedy request runs with the expected-cost rule, with `--dspark-confidence 0.6`, and without `--dspark`
- **THEN** the three runs generate identical tokens

### Requirement: Threshold rule on request
`--dspark-confidence X` SHALL select the threshold rule that `320` defined, with threshold X. `DS4_DSPARK_DISABLE_COST_RULE=1` SHALL select it with the default threshold.

#### Scenario: Explicit threshold
- **WHEN** the CLI runs with `--dspark --dspark-confidence 0.6`
- **THEN** each cycle drafts the longest prefix whose confidence is at or above 0.6

#### Scenario: Switch
- **WHEN** the CLI runs with `--dspark` and `DS4_DSPARK_DISABLE_COST_RULE=1`
- **THEN** its drafts, counters and tokens are those of the threshold rule at the default threshold

### Requirement: Support file in Q2-class expert types
The support-file check SHALL accept a V4.1 DSpark support GGUF whose routed experts use the main model's Q2-class types, with the same metadata rules as any other support file.

#### Scenario: Q2 support file
- **WHEN** `--mtp-model` names a V4.1 DSpark support GGUF with Q2-class experts
- **THEN** the engine loads it and greedy output with `--dspark` stays identical to output without it
