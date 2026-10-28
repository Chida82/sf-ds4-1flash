# Spec Delta

## ADDED Requirements

### Requirement: Closure-gap probe
The engine SHALL offer a probe-category environment switch that, when set to a
path, appends to that file for every think-phase forward of a V4.1 session the
logit margin the `</think>` exit has to cross, `gap = logit[argmax] −
logit[</think>]`, with the in-phase token position and whether the token just fed
ended a line. The probe SHALL leave the generated tokens unchanged and SHALL frame
each generation so base and steered traces can be told apart offline.

#### Scenario: Think-phase trace
- **WHEN** `DS4_V41_CLOSURE_GAP_TRACE=<path>` is set and a session generates in the
  thinking phase, steered or not
- **THEN** the file gains one `gap` line per think-phase forward with the in-phase
  position, the argmax id, the gap in logits and the line-end flag, framed by a
  `begin` line (prompt length, steered flag, opening phase) and an `exit` line when
  `</think>` is emitted

#### Scenario: Probe is silent by default
- **WHEN** the switch is unset
- **THEN** nothing is written and the decode path is the pre-change one

#### Scenario: Output unchanged
- **WHEN** the same prompt runs with and without the switch
- **THEN** the generated tokens are identical: the probe only reads the logits

### Requirement: Steering-site capture probe
The engine SHALL offer a probe-category environment switch that, when set to a path,
records for every decode forward the state read by each layer's attention at the V4.1
steering site, after any steering edits, as raw per-layer rows appended to that file,
with one index line per token (in-phase position, phase, fed token) beside it. The
capture SHALL leave the generated tokens unchanged.

#### Scenario: Capture on a benign reasoning prompt
- **WHEN** `DS4_V41_SITE_CAPTURE=<path>` is set and a session decodes
- **THEN** `<path>` grows by one block of 40 rows of 5120 float32 per decode token and
  `<path>.idx` by one line `t=<pos> think=<0|1> fed=<id>`, and the output tokens match
  the run without the switch

### Requirement: Additive closure channel
A steering profile MAY declare a `closure` object: a third per-layer direction, applied
additively at the V4.1 steering site after the fold slots, `h += a(t)·c[layer]`, in the
thinking phase only, with `a(t)` set per token by the closure onset schedule. A profile
without `closure` SHALL behave bitwise as before.

#### Scenario: No dispatch at zero scale
- **WHEN** a profile declares `closure` and `a(t)` is 0 for this token (before the
  onset, or in the answer phase)
- **THEN** no additive operation is dispatched and the layer input equals the one the
  fold slots alone produce

#### Scenario: Profile without closure
- **WHEN** a profile declares only fold slots
- **THEN** the run is bitwise identical to the pre-change engine

### Requirement: Closure onset schedule
`a(t)` SHALL be 0 for the first `T0(N)` in-phase think tokens, where `N` is the prompt's
reasoning-effort level (unknown counts as 75) and `T0` runs linearly from `onset_min` at
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

### Requirement: Closure second stage
When the `closure` object declares a second stage (`scale2 ≥ scale`, `after_tokens`,
`ramp2_tokens`), `a(t)` SHALL rise again by a cubic smoothstep from `scale` to `scale2` over
`ramp2_tokens` tokens starting `after_tokens` tokens past `T0(N)`. Without it the schedule
SHALL be single-stage.

#### Scenario: Second stage
- **WHEN** a profile declares `scale` 0.4, `after_tokens` 2000, `scale2` 0.9, `ramp2_tokens` 512
- **THEN** `a(t)` holds 0.4 from the end of the first ramp until onset + 2000, then rises to
  0.9 over the next 512 tokens; a profile without `scale2` runs bitwise as before

#### Scenario: Validation of the closure object
- **WHEN** `closure` declares `scale ≤ 0`, `onset_min < 0`, `onset_max < onset_min`,
  a non-integer onset or ramp, `scale2 < scale`, a second stage without `after_tokens`,
  or the file lacks the extra matrix
- **THEN** the engine refuses to start, naming the file and the fault
