# Spec Delta

## MODIFIED Requirements

### Requirement: Closure onset schedule
`a(t)` SHALL be 0 for the first `T0(N)` in-phase think tokens, where `N` is the prompt's
reasoning-effort level, the level its effort line carries (75 for the named high level,
100 for max, the number for a numeric level; a mode without an effort line counts as 75),
and `T0` runs linearly from `onset_min` at
`N ≤ 10` to `onset_max` at `N = 100`; it SHALL then rise by a cubic smoothstep to `scale`
over `ramp_tokens` tokens and stay there, and SHALL be 0 in the answer phase.

#### Scenario: Non-think runs and the answer phase are untouched
- **WHEN** a profile with `closure` runs with thinking off, or a think run has
  emitted `</think>`
- **THEN** the output is bitwise identical to the same profile without `closure`
  (the shipped 418-C answer schedule, 7 → 4, runs unchanged)

#### Scenario: Onset follows the reasoning-effort level
- **WHEN** the same profile runs at think-level 10, 75 and 100 with `onset_min` 256 and
  `onset_max` 2560
- **THEN** the additive scale starts rising at think token 256, 1920 and 2560
  respectively

#### Scenario: Frontend supplies the level
- **WHEN** the CLI runs with `--think-level N`
- **THEN** the session's level is `N`; a session whose frontend never set it uses 75

#### Scenario: Named max places the onset at level 100
- **WHEN** a steered thinking run uses the named `max` mode (server `reasoning_effort` `max`, or CLI `/think-max`)
- **THEN** the closure onset is placed for level 100, the level the prompt's effort line tells the model, not for 75
