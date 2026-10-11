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

### Requirement: Support file in Q2-class expert types
The support-file check SHALL accept a V4.1 DSpark support GGUF whose routed experts use the main model's Q2-class types, with the same metadata rules as any other support file.

#### Scenario: Q2 support file
- **WHEN** `--mtp-model` names a V4.1 DSpark support GGUF with Q2-class experts
- **THEN** the engine loads it and greedy output with `--dspark` stays identical to output without it
