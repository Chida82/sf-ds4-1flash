# Spec Delta

## ADDED Requirements

### Requirement: A schema-first layout shares the questions across states
With `"sf":{"layout":"schema_first"}` or `--sysone-layout schema_first`, the
server SHALL place all question definitions before the state, cache the
session state after the definitions keyed by their tokens, and answer each
question from a pointer suffix that does not repeat its definition. The
default layout SHALL remain `state_first`.

#### Scenario: Second state on the same schema
- **WHEN** two requests carry the same questions in the same order and different states
- **THEN** the second reports a schema cache hit and prefills only its state

#### Scenario: Per-question cost
- **WHEN** a request has five questions
- **THEN** each question's suffix is under 16 tokens

#### Scenario: Answers never chain
- **WHEN** a request has three questions
- **THEN** each is read from the same saved state, and repeating the request gives bitwise equal logits

### Requirement: The layout is kept only if it costs no accuracy
The layout SHALL be accepted only when its accuracy on the bench is not below
`state_first` by more than one point (95% bootstrap interval) and its median
latency per decision on a cached schema is at most half.

#### Scenario: Recorded decision
- **WHEN** the bench runs finish
- **THEN** `sysone-bench/record.md` holds both layouts' rows and the decision

### Requirement: Prior correction is optional and measured
With `"sf":{"prior_correction":true}` under `schema_first`, the server SHALL
subtract from each `noul` and `choice` option logit that option's centred
logit measured once per schema on an empty state. It SHALL be kept only if it
lowers the rotation flip rate without lowering accuracy.

#### Scenario: Correction reported
- **WHEN** a request asks for prior correction
- **THEN** the response's `sf` object says so and `legal_mass` is the uncorrected value

### Requirement: Calibration is per layout
A calibration file SHALL apply only to the layout in its binding.

#### Scenario: Request picks the other layout
- **WHEN** the server holds a `state_first` calibration and a request uses `schema_first`
- **THEN** the request is answered at temperature 1 and its `sf` object reports `"calibration":"none"`

#### Scenario: Server default picks the other layout
- **WHEN** the server starts with `--sysone-layout schema_first` and a `state_first` calibration file
- **THEN** it exits at startup with a message naming the layout
