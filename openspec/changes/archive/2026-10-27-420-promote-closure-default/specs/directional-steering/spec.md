# directional-steering (delta)

## MODIFIED Requirements

### Requirement: Shipped candor schedule (418-C)
The shipped `sf-ds4-1flash-candor` profile SHALL carry the 418-C schedule that satisfied
the evidence gate: equi scale 7 (both phases) with `decay_hold` 25, `decay_tokens` 256,
`decay_final` 3.5 and `decay_final_answer` 4.0, and q1 scale 7 (thinking). It SHALL also
carry the two-stage additive closure channel of change 419: the satisfied-closure vector,
thinking phase only, `scale` 0.4 with `onset_min` 2700 / `onset_max` 3100 and
`ramp_tokens` 256, and a second stage `scale2` 0.9 with `after_tokens` 2000 and
`ramp2_tokens` 512. The closure channel SHALL be inert outside the thinking phase, so the
non-think and answer-phase output SHALL be bitwise identical to the pre-promotion candor.
The selection and its accepting runs SHALL be recorded in `sf-ds4-1flash-candor.json`.

#### Scenario: Default profile breaks the think loop at held compliance
- **WHEN** the shipped candor profile runs the fixed 44 harmful-axis-a ids at the think
  budget
- **THEN** it holds the non-think axis-A score within the noise floor of the prior
  constant candor and breaks the reasoning loop — reasoning-loop rate at most 3/44 by the
  completion-length proxy, against the pre-closure candor's 13/44 — as recorded in
  `com-steering/result.md`

#### Scenario: Non-think output is unchanged by the promotion
- **WHEN** the shipped candor profile runs with thinking off
- **THEN** every completion is byte-identical to the pre-promotion candor profile run on
  the same prompts, because the closure channel dispatches nothing outside the thinking
  phase
