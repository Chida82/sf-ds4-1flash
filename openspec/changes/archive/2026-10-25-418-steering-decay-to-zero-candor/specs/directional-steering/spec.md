# Spec Delta

## ADDED Requirements

### Requirement: Profile-carried residual decay schedule
A residual steering slot loaded from a profile MAY declare a decay window `decay_tokens`
(N) and a final scale `decay_final` (F) that ease the slot's scale from its start scale S
down to F over the first N in-phase tokens with a cubic smoothstep, then hold at F. The
curve SHALL only decrease (`F ≤ S`). The schedule SHALL bind the V4.1 residual site only
(FFN and attention stay refused, `401`) and SHALL be carried only through the profile, not
through `--dir-steering-*` options.

#### Scenario: Decaying smoothstep from start scale to final
- **WHEN** a slot with start scale S, final `F` (`0 ≤ F ≤ S`) and window `N > 0` scales
  the computation for in-phase position `p`
- **THEN** the applied scale is `S − (S − F)·(3t² − 2t³)` with `t = clamp(p/N, 0, 1)`,
  equal to S at `p = 0` and holding at F for `p ≥ N`

#### Scenario: Zero window is the constant path, bitwise
- **WHEN** a profile's slot omits the decay fields or sets `decay_tokens` to zero
- **THEN** the run's logits, KV and Engram match the constant-scale run of the same slot
  bitwise

#### Scenario: Release to zero frees the body
- **WHEN** a slot sets `decay_final` to `0` with `N > 0`
- **THEN** the first in-phase tokens receive the full start scale and, from position `N`,
  that slot contributes nothing, so later tokens are computed as by the unsteered model
  for that slot

### Requirement: Per-phase decay reset
The decay position counter SHALL be per session and SHALL reset at the think→answer
boundary, so a slot active in both phases runs an independent curve in each. The boundary
SHALL be taken from the prompt's final token (opening phase) and the end-of-thinking
token (switch), consistent with the per-slot reasoning-phase gate. A slot gated to one
phase SHALL apply its schedule only within that phase and zero outside it.

#### Scenario: Answer dose restarts after a long thinking block
- **WHEN** a both-phase slot's thinking phase runs past its own decay window and the
  answer phase then begins
- **THEN** the answer phase starts again at the start scale S and decays over its own
  window, not continuing from the thinking phase's decayed tail

#### Scenario: First answer token is scheduled
- **WHEN** a schedule starts at a nonzero start scale
- **THEN** the final prompt forward that predicts the first answer token already uses the
  start scale at position `p = 0`, not a later value

#### Scenario: Think-gated slot decays only in thinking
- **WHEN** a slot gated to the thinking phase declares a decay window
- **THEN** it decays over its window inside the thinking phase and stays zero in the
  answer phase, unaffected by the answer boundary reset

### Requirement: Decay field validation
A profile declaring decay fields SHALL be refused unless `decay_tokens` is a non-negative
integer and `decay_final` is a finite number with `0 ≤ decay_final ≤ scale` for that
slot. A profile that declares neither field SHALL load and behave exactly as before this
change. The decay fields SHALL be optional profile metadata that, like the existing
provenance fields, do not change the profile's admission as its own opt-in.

#### Scenario: Out-of-range final scale is refused
- **WHEN** a slot declares `decay_final` greater than its `scale`, or a negative or
  non-finite value, or a negative `decay_tokens`
- **THEN** the engine refuses to start, naming the slot and the offending field

#### Scenario: A profile without decay fields is unchanged
- **WHEN** a profile carries no `decay_tokens` or `decay_final` on any slot
- **THEN** it loads and runs identically to its behavior before this change

### Requirement: Decay schedule is evidence-gated
The decay schedule SHALL be retained as release behavior only after a verdict run holds
the axis-A score within the measurement noise floor of the standing constant candor
profile while a fidelity or quality metric improves. A negative or inconclusive result
SHALL leave the shipped constant profile as the release behavior.

#### Scenario: No established benefit
- **WHEN** the decay profile does not hold the axis-A score within the noise floor, or
  shows no measured fidelity benefit
- **THEN** the findings are recorded and the shipped `sf-ds4-1flash-candor` profile stays
  the release configuration

### Requirement: Profile-carried hold, per-phase answer final, and cyclic ramp (418-C)
A residual steering slot loaded from a profile MAY additionally declare a plateau
`decay_hold` (H), an answer-phase final override `decay_final_answer` (Fa), and a
think-only cyclic ramp `ramp_tokens`/`ramp_low`. These SHALL be optional profile metadata
carried only through the profile, SHALL bind the V4.1 residual site only, and SHALL leave
a profile that declares none of them bitwise identical to its pre-change behavior.

#### Scenario: Hold then decay
- **WHEN** a slot declares `decay_hold` H with a decay window N > 0
- **THEN** the applied scale holds at the start scale S for the first H in-phase tokens,
  then eases S→F over the next N tokens by the smoothstep, i.e. `t = clamp((p − H)/N, 0, 1)`

#### Scenario: Answer phase uses its own final
- **WHEN** a both-phase slot declares `decay_final_answer` Fa and the run is in the answer
  phase (or a non-think run, which is the answer phase throughout)
- **THEN** the decay eases toward Fa in the answer while the thinking phase still eases
  toward `decay_final`; a slot that omits `decay_final_answer` uses `decay_final` in both

#### Scenario: Cyclic ramp in thinking only
- **WHEN** a slot declares `ramp_tokens` N and `ramp_low` L with the ramp active
- **THEN** inside the thinking phase the scale rides S→L over N tokens, holds L for N,
  rises L→S over N and repeats (period 3N), and stays at the plain scale in the answer

#### Scenario: Validation of the 418-C fields
- **WHEN** a slot declares `decay_hold` < 0, `decay_final_answer` outside `0 ≤ Fa ≤ scale`,
  or `ramp_tokens` < 0 or `ramp_low` outside `0 ≤ L ≤ scale`
- **THEN** the engine refuses to start, naming the slot and the offending field

### Requirement: Shipped candor schedule (418-C)
The shipped `sf-ds4-1flash-candor` profile SHALL carry the 418-C schedule that satisfied
the evidence gate: equi scale 7 (both phases) with `decay_hold` 25, `decay_tokens` 256,
`decay_final` 3.5 and `decay_final_answer` 4.0, and q1 scale 7 (thinking). The selection
and its accepting runs SHALL be recorded in `sf-ds4-1flash-candor.json`.

#### Scenario: Default profile breaks the think loop at held compliance
- **WHEN** the shipped candor profile runs the fixed 44 harmful-axis-a ids at the think
  budget (MT=8192)
- **THEN** it holds the non-think axis-A score within the noise floor of the prior
  constant candor and reduces the reasoning-loop rate versus that constant, as recorded in
  `com-steering/result.md`
