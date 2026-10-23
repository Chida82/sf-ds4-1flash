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

### Requirement: Scheduled scale curve
The retained schedule SHALL decay the scale from a start maximum down to a residual minimum over an N-token window using a cubic smoothstep, then hold at the residual; the curve decreases, it does not ramp up. It SHALL bind the V4.1 residual site, the only live hook (FFN and attention refused, `401`), and `N = 0` SHALL reproduce the constant intervention bitwise.

#### Scenario: Decaying smoothstep from max to residual
- **WHEN** a schedule with start maximum S, final residual F (F < S) and window N (> 0) tokens scales the computation for in-phase position `p` with `0 ≤ p < N`
- **THEN** the applied scale is `S − (S − F)·(3t² − 2t³)` with `t = p/N` — equal to S at `p = 0` and easing down to F — and for `p ≥ N` it holds at F

#### Scenario: Dose that breaks the refusal then eases off
- **WHEN** the start maximum breaks the refusal in the first in-phase tokens and the residual F is small (e.g. a mild 0.2 the vector keeps)
- **THEN** the first tokens get the full dose and later tokens are steered progressively less, down to the residual, so the body of the response stays close to the base model once the refusal is passed

### Requirement: Per-phase schedule across thinking and answer
A retained phase schedule SHALL run an independent curve in the thinking phase and in the answer phase, with the boundary taken from the thinking start/end token ids and the position counter reset at the answer boundary. Omitting the thinking controls SHALL leave the single-schedule behavior unchanged.

#### Scenario: Answer dose restarts after a long thinking block
- **WHEN** the thinking phase runs past its own decay window and the answer phase then begins
- **THEN** the answer phase starts at its own start scale and decays over its own window, not continuing from the thinking phase's decayed tail

#### Scenario: Thinking controls omitted
- **WHEN** only the answer-phase schedule is configured and the thinking controls are omitted
- **THEN** behavior is unchanged from the single retained schedule and no thinking-specific vector or decay is applied
