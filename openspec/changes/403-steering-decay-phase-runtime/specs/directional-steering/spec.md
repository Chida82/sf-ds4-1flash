# Spec Delta

## ADDED Requirements

### Requirement: Residual steering scale decay
The residual steering scale SHALL follow a cubic smoothstep
`start + (final - start) * (3t^2 - 2t^3)`, `t = generated / decay_tokens` clamped to
`[0,1]`, set by `--dir-steering-residual-decay-tokens N` and
`--dir-steering-residual-decay-final F`. With `N = 0` the scale SHALL be the constant
`start`, leaving `401`'s behavior and the no-op gate unchanged.

#### Scenario: Strong start, small residual
- **WHEN** start 0.5, decay-tokens 20, final 0.05 are set
- **THEN** the applied scale is 0.5 at the first generated token and 0.05 from the
  20th on

#### Scenario: Decay off is the constant
- **WHEN** `--dir-steering-residual-decay-tokens 0` is set with a loaded vector
- **THEN** every generated token uses the constant start scale, bitwise identical to
  `401`

### Requirement: Think-phase steering schedule
The engine SHALL detect `<think>`/`</think>` in the generated tokens and, inside a
think block, apply the think scale (and the think vector if `--dir-steering-think-file`
is given), else the answer scale. The decay counter SHALL restart at each phase change,
measuring `generated` from the later of the generation start and the phase start.

#### Scenario: Answer schedule survives a long think block
- **WHEN** the model emits 100 think tokens, then `</think>`, with distinct think and
  answer schedules
- **THEN** the first answer token uses the answer start scale, not the think final
  scale

#### Scenario: One vector, two schedules by default
- **WHEN** no `--dir-steering-think-file` is given
- **THEN** both phases steer with the answer vector, each under its own scale schedule
