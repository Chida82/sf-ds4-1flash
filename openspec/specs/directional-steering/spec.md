# directional-steering Specification

## Purpose
Provide explicit, experimental directional-steering admission on V4.1 while preserving the default startup refusal and unsteered behavior.

## Requirements

### Requirement: V4.1 weighted-fold intervention
A profile slot with scale `F` SHALL apply `h -= F*d[L]*dot(d[L],h)` to the weighted HC attention-input fold of layers 1-39, after Engram where present and before normalization. There SHALL be no command-line scale for this site. This site SHALL NOT be represented as a verified replica of the published mean-residual pre-Engram hook.

#### Scenario: Direct layer mapping
- **WHEN** row N is active in a valid direction matrix
- **THEN** it edits the attention-input fold of layer N, not the FFN output or all four persistent residual copies

#### Scenario: Over-projection has explicit semantics
- **WHEN** a unit direction is applied at scales 1, 2, 4 and 8
- **THEN** its component is respectively removed, reflected, multiplied by -3 and multiplied by -7 before normalization

#### Scenario: No residual-site option
- **WHEN** `--dir-steering-residual` is passed to the CLI, eval or server
- **THEN** the binary rejects it as an unknown option and exits 2

### Requirement: Consistent enabled rounding and coverage
The enabled intervention SHALL apply the same projection/rounding order on every route that produces an attention input; that order is fixed by a route-agreement test, not asserted. Decode, batch prefill and reconstructed attention-key paths SHALL apply this contract exactly once per applicable input. Disabled computation SHALL retain its prior arithmetic and schedule.

#### Scenario: Ordinary wide prefill
- **WHEN** a wide prefill uses decoder suffix publication or warming, including short-wide prompts
- **THEN** reconstructed attention inputs receive the same intervention order as directly processed inputs

#### Scenario: Isolated row agreement
- **WHEN** the same synthetic folded rows are processed by single-row and batch intervention paths
- **THEN** they obey the same rounding/projection contract within the documented arithmetic test tolerance

### Requirement: Strict control-vector conversion
The converter SHALL accept the complete 39-row V4.1 control-vector layer set with supported layout, consistent metadata, finite unit F32 rows and width 5120. It SHALL write a 40x5120 f32 file with row 0 zero and source row N at row N. Invalid input SHALL fail with its cause before output is written.

#### Scenario: Missing or nonfinite row
- **WHEN** any required row is missing, duplicated, truncated, nonfinite or outside the norm tolerance
- **THEN** conversion fails and produces neither a new vector nor a new sidecar

#### Scenario: Mapping is distinguishable
- **WHEN** a fixture with distinct directions in each layer is converted
- **THEN** the 819200-byte output preserves every layer's direction and indexing

### Requirement: Source and application metadata
Converted-vector metadata SHALL distinguish source hook and source alpha from the runtime application hook and intervention revision. It SHALL record source provenance, base revision when available and output content hash. Historical screening scales SHALL NOT be advertised as validated defaults.

#### Scenario: Source alpha is not a runtime recommendation
- **WHEN** a source declares alpha 0.5 and a different derivation hook
- **THEN** conversion preserves that source information without asserting equivalent behavior at runtime scale 0.5 or recommending 4-8 as a validated range

### Requirement: Runtime vector validation
Active steering SHALL require an exact-size finite f32 matrix, finite supported scales, zero row 0, and zero or unit-normalized remaining rows within the documented tolerance. Invalid files SHALL fail clearly without silently normalizing values or substituting missing data.

#### Scenario: Masked layer
- **WHEN** a valid layer row is all zero
- **THEN** its projection makes no change while the other valid rows remain active

### Requirement: Unsupported active-site diagnostics
On V4.1 the CLI SHALL keep upstream's `--dir-steering-file`, FFN/attention options and live FFN API, and SHALL refuse a raw direction file at engine open with upstream's unchanged message. Unsupported nonzero application requests SHALL be rejected, never reported as success without an edit. The server and eval SHALL NOT accept these options.

#### Scenario: Legacy file-only default
- **WHEN** a V4.1 CLI invocation supplies `--dir-steering-file` without a profile, with or without an FFN or attention scale
- **THEN** startup prints upstream's exact refusal and exits 1

#### Scenario: Live FFN change
- **WHEN** a V4.1 session receives a nonzero live FFN steering request
- **THEN** it returns an unsupported-site error and does not claim to change residual steering

#### Scenario: Server and eval have no raw options
- **WHEN** `--dir-steering-file`, `--dir-steering-ffn` or `--dir-steering-attn` is passed to the server, or `--dir-steering-file` to the eval
- **THEN** it is rejected as an unknown option and the binary exits 2

### Requirement: Steering and persistent state
While a session's steering is on, automatic persistent KV reuse and explicit snapshot save/load SHALL be refused with a clear error before any session mutation, unless the frontend has declared for that session that it keeps steered persistent state apart, bound to the profile's identity. Sessions with steering off, and sessions of an engine without a profile, SHALL keep existing persistent-state behavior. A steered session SHALL NOT read, rewrite or delete cache files outside the store its frontend reserves for it.

#### Scenario: Steered session with a KV root
- **WHEN** a server with a configured KV root runs a session with steering on
- **THEN** that session's persistent lookup, load and store use only the server's steering store, bound to the loaded profile, and never the root

#### Scenario: Snapshot while steered
- **WHEN** snapshot save or load is requested on a session with steering on whose frontend has made no such declaration, including while a gated slot is at zero for the current token
- **THEN** it fails clearly before changing the session's tokens, logits or KV

### Requirement: Runtime no-op evidence
Disabled steering and a zero-direction control at nonzero scale SHALL preserve baseline logits, KV and Engram bitwise under the same schedule. Release evidence SHALL include state comparisons, route coverage and enabled overhead; matching completion text alone SHALL NOT establish bitwise correctness.

#### Scenario: Slow-path control
- **WHEN** a zero vector is used at nonzero residual scale for 65 decoded steps
- **THEN** state and logits match baseline even though the intervention path is exercised

### Requirement: Second residual direction
A profile MAY declare a second slot: a per-layer unit direction with its own scale, applied as a second in-place weighted fold after the first on every route that applies the first. It SHALL share the first slot's disable switch, persistence rule and loader validation.

#### Scenario: Applied on every route of the first fold
- **WHEN** a second direction is active
- **THEN** the token-major decode, prefill-batch and decoder-suffix routes each apply
  the second fold immediately after the first

#### Scenario: Second file without the opt-in
- **WHEN** `--dir-steering-file-2` is passed to any binary
- **THEN** it is rejected as an unknown option and the binary exits 2; a second direction exists only as a profile slot

#### Scenario: Zero second scale is the single-direction run
- **WHEN** a profile declares only its first slot
- **THEN** no second direction is loaded and the run applies the first fold alone

#### Scenario: Scale without a file
- **WHEN** `--dir-steering-residual-2` is passed to any binary
- **THEN** it is rejected as an unknown option and the binary exits 2

### Requirement: Composition of two folds is stated honestly
Two sequential folds SHALL be documented as sequential removals. The run identity
SHALL record the per-layer cosine between the two loaded directions, and the term
"rank-2 span removal" SHALL be used only for pairs whose median absolute cosine is
below the documented orthogonality threshold. The runtime SHALL NOT refuse a
non-orthogonal pair.

#### Scenario: Orthogonal pair nulls both projections
- **WHEN** the two directions are orthogonal per layer and both scales are 1
- **THEN** after the two folds the projections of the activation onto both directions
  are zero within tolerance, independent of fold order

#### Scenario: Non-orthogonal pair is recorded, not refused
- **WHEN** the two directions have median absolute cosine above the threshold
- **THEN** the run proceeds, the identity records the cosine, and the report describes
  the arm as two sequential folds

### Requirement: Rank-2 run identity
A run with a second direction SHALL carry a `rank2` record (second file hash, second
scale, per-layer cosine to the first) inside its intervention identity, so that it is
never cached, compared or reported as a rank-1 run.

#### Scenario: Identity distinguishes rank-1 and rank-2
- **WHEN** two runs differ only in the presence of a second direction
- **THEN** their intervention identities differ and the harness treats them as distinct arms

### Requirement: Per-slot reasoning-phase gate
Each residual steering slot SHALL accept a gate confining it to the thinking phase or
to the answer phase. A gated slot SHALL apply its constant scale while the session is
in its phase, and a scale of zero otherwise. The phase SHALL be tracked per session,
opening according to the prompt's final token and switching when the end-of-thinking
token is generated. No gate SHALL mean both phases.

#### Scenario: A think-gated slot is absent from the answer
- **WHEN** a slot is gated to the thinking phase and generation passes the
  end-of-thinking token
- **THEN** that slot's scale becomes zero for the remaining tokens, and the other
  slot's scale is unaffected

#### Scenario: Gates come from the environment or from a profile
- **WHEN** a loaded profile declares a phase for a slot, or `DS4_STEERING_THINK_PHASE` / `DS4_STEERING_THINK_PHASE2` is set
- **THEN** the profile's phase gates that slot, a slot without one runs in both phases, and the environment variables are not read

#### Scenario: Both-phase gating is the unchanged path
- **WHEN** neither slot is gated
- **THEN** the session performs no phase tracking and the run matches the ungated run

#### Scenario: Gated sessions do not share a batch
- **WHEN** a decode batch is assembled and any of its sessions has steering on while the profile carries a gate or a schedule, or its sessions differ in steering
- **THEN** the native batched path is declined and the sessions decode one at a time,
  since one batched forward applies a single scale to every row; a batch whose sessions all have steering off is batched even with such a profile loaded

### Requirement: Steering profile file
The CLI and eval SHALL accept `--steering-profile`, and the server `--steering-profile-on-request`, naming one file that carries every slot's
direction matrix, its constant scale and its phase gate. The file SHALL be an
eight-byte magic, a little-endian `uint32` header length, a JSON header declaring the
intervention site, the matrix shape and one or two slots, then one direction matrix per
slot in slot order.

#### Scenario: A profile replaces the option set
- **WHEN** a profile is loaded
- **THEN** it is the run's whole steering configuration, and the run computes byte-identically to the same profile before the raw options were removed

#### Scenario: A bare name resolves, and a wrong one lists the alternatives
- **WHEN** the argument is not a readable path
- **THEN** it is resolved as a profile name in the repository's profile directory, and
  if nothing matches, the engine lists the profiles that exist

#### Scenario: The server's flag loads the same file
- **WHEN** the server is started with `--steering-profile-on-request` and a profile name
- **THEN** it resolves and validates the profile exactly as the CLI's `--steering-profile` does, and applies it only to requests that select steering

### Requirement: Profile admission and validation
A profile SHALL be refused unless its header names the engine's own site and matrix
shape, each slot carries a nonzero scale and a phase of `both`, `think` or `answer`,
and the file's size equals the header plus one matrix per declared slot. Each matrix
SHALL pass the validation a direction file passed on its own receives. A profile SHALL
be the only admission of steering on V4.1, and SHALL NOT be combined with `--dir-steering-file`, `--dir-steering-ffn` or `--dir-steering-attn`.

#### Scenario: A profile is its own opt-in
- **WHEN** a profile is given
- **THEN** the engine starts and applies the profile; no flag or environment variable exists or is needed to admit it

#### Scenario: Profile and raw options together are refused
- **WHEN** a CLI invocation gives a profile together with `--dir-steering-file`, `--dir-steering-ffn` or `--dir-steering-attn`
- **THEN** the engine refuses to start, naming the conflict

#### Scenario: A truncated or over-long profile is refused
- **WHEN** the file's size does not equal the header plus one matrix per declared slot
- **THEN** the engine refuses to start, reporting the size it found and the size the
  header promises

#### Scenario: A foreign site or shape is refused
- **WHEN** the header declares a site or a matrix shape that is not this engine's
- **THEN** the engine refuses to start, naming the site and shape it requires

### Requirement: Profile provenance is carried, not interpreted
A profile header SHALL be able to carry a name, a description, and for each slot the
source vector's filename and the SHA-256 of the matrix bytes the profile holds. The
engine SHALL NOT depend on those fields.

#### Scenario: Identifying a profile found later
- **WHEN** a profile file is inspected
- **THEN** its header names the configuration and the vectors it was built from, and
  each matrix can be checked against its recorded hash

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

### Requirement: Profile-carried hold and per-phase answer final (418-C)
A residual steering slot loaded from a profile MAY additionally declare a plateau
`decay_hold` (H) and an answer-phase final override `decay_final_answer` (Fa). These SHALL be optional profile metadata
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

#### Scenario: Validation of the 418-C fields
- **WHEN** a slot declares `decay_hold` < 0 or `decay_final_answer` outside `0 ≤ Fa ≤ scale`
- **THEN** the engine refuses to start, naming the slot and the offending field

#### Scenario: Retired slot keys are refused
- **WHEN** a slot declares `decay_phase`, `ramp_tokens` or `ramp_low` (the 418 decay phase
  and 418-B cyclic ramp, explored and not adopted)
- **THEN** the engine refuses to start, naming the file, the slot and the key, instead of
  running the profile without it

### Requirement: Shipped candor schedule (418-C)
The shipped `sf-ds4-1flash-candor` profile SHALL carry the 418-C schedule that satisfied
the evidence gate: equi scale 7 (both phases) with `decay_hold` 25, `decay_tokens` 256,
`decay_final` 3.5 and `decay_final_answer` 4.0, and q1 scale 7 (thinking). It SHALL also
carry the two-stage additive closure channel of change 419: the satisfied-closure vector,
thinking phase only, `scale` 0.4 with `onset_min` 2700 / `onset_max` 3100 and
`ramp_tokens` 256, and a second stage `scale2` 0.9 with `after_tokens` 2000 and
`ramp2_tokens` 512. The closure channel SHALL be inert outside the thinking phase, so the
non-think and answer-phase output SHALL be bitwise identical to the pre-promotion candor.
The selection and its accepting runs SHALL be recorded in `com-steering/README.md` ("Directions (provenance)") and `com-steering/result.md`.

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

### Requirement: Per-session steering switch
Each session SHALL carry a steering switch. A session SHALL start with it on when its engine loaded a profile, and off otherwise. Turning it on in an engine without a profile SHALL fail with an error and leave the session unchanged.

#### Scenario: Default follows the profile
- **WHEN** a session is created by an engine that loaded a profile
- **THEN** its steering is on, and a run that never touches the switch computes exactly as before this change

#### Scenario: No profile, no steering
- **WHEN** a frontend turns steering on for a session whose engine loaded no profile
- **THEN** the call returns an error naming the missing profile and the session stays unsteered

#### Scenario: Distributed sessions keep their default
- **WHEN** a frontend changes the switch on a distributed or network tensor-parallel session
- **THEN** the call returns an error and the switch keeps its value

### Requirement: Switched-off session is the unsteered model
A session whose steering is off SHALL compute exactly as a session of an engine opened without the profile: the same logits, KV state and Engram history, bit for bit, on every route.

#### Scenario: Profile loaded, session off
- **WHEN** an engine with the shipped profile runs a session with steering off for a prefill and 65 decoded tokens
- **THEN** its logits, KV and Engram history equal, bitwise, those of the same run on an engine opened without the profile

### Requirement: Switching drops live state
Changing a session's switch while the session holds evaluated tokens SHALL discard that state before the next evaluation, so no state computed under one setting is extended under the other. Setting the switch to its current value SHALL change nothing.

#### Scenario: Switched after a prefill
- **WHEN** a steered session evaluates a prompt, its switch is turned off, and the same prompt is synced again
- **THEN** the whole prompt is evaluated again, and the result equals, bitwise, a fresh session with steering off

#### Scenario: Same value is a no-op
- **WHEN** the switch is set to the value it already has
- **THEN** the session keeps its tokens, KV and logits
