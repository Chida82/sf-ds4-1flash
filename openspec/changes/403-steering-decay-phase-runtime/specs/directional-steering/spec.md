# Spec Delta

## ADDED Requirements

### Requirement: Evidence-gated temporal steering
A temporal mechanism SHALL be retained only after comparison with a comparably tuned constant baseline under a pinned intervention and held-out protocol. The decision SHALL identify a measured benefit and non-inferior behavior/quality guards. Negative or inconclusive experiments SHALL NOT create permanent runtime options by default.

#### Scenario: No established benefit
- **WHEN** windowed and decaying candidates do not establish the declared adoption criterion
- **THEN** the findings are recorded and constant steering remains the release behavior without new schedule controls

### Requirement: Retained schedule contract
If a schedule is retained, its shape, prompt policy, start/final scales and counting convention SHALL be documented, and its inputs SHALL be finite and validated. Zero decay duration SHALL reproduce the constant intervention bitwise.

#### Scenario: Constant fallback
- **WHEN** decay duration is zero
- **THEN** output matches the corresponding constant `401` intervention bitwise

### Requirement: Scheduled first token
A retained schedule SHALL define the scale for the computation predicting each output token, including the first answer logits produced during prompt processing.

#### Scenario: First token is scheduled
- **WHEN** a retained schedule starts at a nonzero scale
- **THEN** the final prompt forward that predicts the first answer token already uses that starting scale

### Requirement: Session-local schedule state
Retained schedule state SHALL be per session. Unsupported batching and persistent prefix reuse SHALL fail clearly rather than share a counter or cached state, and snapshots SHALL stay refused for a nonconstant mode under the `401` guard.

#### Scenario: Interleaved sessions
- **WHEN** two supported sessions at different output positions execute interleaved
- **THEN** each uses its own scale and phase, matching its independent trajectory

### Requirement: Conditional phase and second vector
A thinking/answer phase schedule, and separately a second direction file, SHALL each require a measured phase-specific benefit over the simpler design before any control is added.

#### Scenario: Phase split without measured benefit
- **WHEN** a thinking/answer phase schedule is proposed without a measured phase-specific gap over the same-vector single schedule
- **THEN** no phase control is added and the decision is recorded
