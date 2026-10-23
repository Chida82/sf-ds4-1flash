# directional-steering Specification

## Purpose
Provide explicit, experimental directional-steering admission on V4.1 while preserving the default startup refusal and unsteered behavior.

## Requirements

### Requirement: V4.1 steering opt-in
The CLI and server SHALL reject a steering file on V4.1 with the unchanged upstream error unless the explicit opt-in is present. The opt-in SHALL lift only the steering-file restriction, not other unsupported conditions or application-site validation.

#### Scenario: Default path still refuses verbatim
- **WHEN** a steering file is supplied without either opt-in
- **THEN** startup prints the exact upstream refusal and exits 1

#### Scenario: Opt-in lifts only one restriction
- **WHEN** the opt-in, a steering file and explicit zero scales are supplied on supported single-box Metal
- **THEN** the steering-file admission restriction is cleared
- **AND** an independently unsupported setting still causes rejection

### Requirement: Presence-based environment opt-in
The CLI flag SHALL independently enable admission. An unset `DS4_ALLOW_V41_STEERING` SHALL not enable admission; any present value SHALL enable it. Help and documentation SHALL distinguish permission to load steering from actual application or efficacy.

#### Scenario: Environment values retain their existing meaning
- **WHEN** the variable is tested unset, empty, `0`, and `1` without the CLI flag
- **THEN** only the unset case lacks the environment opt-in

### Requirement: Admission-only no-op
With no active steering intervention, enabling admission SHALL allocate no direction tensor and preserve the unsteered logits, KV state and Engram history bitwise.

#### Scenario: Opt-in without a file
- **WHEN** an opted-in session without a steering file decodes 65 tokens
- **THEN** its logits, KV and Engram match the same run without the opt-in bitwise

#### Scenario: File with zero scales
- **WHEN** a valid file is supplied with all steering scales explicitly zero and the opt-in
- **THEN** no direction tensor is allocated and the same state comparison passes

### Requirement: V4.1 weighted-fold intervention
With the opt-in, `--dir-steering-residual F` SHALL apply `h -= F*d[L]*dot(d[L],h)` to the weighted HC attention-input fold of layers 1-39, after Engram where present and before normalization. The scale SHALL default to zero. This site SHALL NOT be represented as a verified replica of the published mean-residual pre-Engram hook.

#### Scenario: Direct layer mapping
- **WHEN** row N is active in a valid direction file
- **THEN** it edits the attention-input fold of layer N, not the FFN output or all four persistent residual copies

#### Scenario: Over-projection has explicit semantics
- **WHEN** a unit direction is applied at scales 1, 2, 4 and 8
- **THEN** its component is respectively removed, reflected, multiplied by -3 and multiplied by -7 before normalization

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
V4.1 SHALL preserve the legacy FFN/attention options and live FFN API but SHALL reject unsupported nonzero application requests rather than report success without an edit. The no-opt-in upstream refusal SHALL retain precedence. Selecting the residual scale explicitly SHALL suppress the implicit FFN scale.

#### Scenario: Legacy file-only default
- **WHEN** an opted-in V4.1 invocation supplies a file and implicitly requests FFN scale 1
- **THEN** it reports that the active FFN site is unsupported and directs the user to explicit residual-site selection

#### Scenario: Live FFN change
- **WHEN** a V4.1 session receives a nonzero live FFN steering request
- **THEN** it returns an unsupported-site error and does not claim to change residual steering

### Requirement: Steering and persistent state
While a nonzero steering scale is active, automatic persistent KV reuse and explicit snapshot save/load SHALL be refused with a clear error before any session mutation. Zero-scale and unsteered sessions SHALL keep existing persistent-state behavior. A steered session SHALL NOT read, rewrite or delete existing cache files. A steering identity descriptor is not required by this change.

#### Scenario: Steered session with a KV root
- **WHEN** a server with a configured KV root starts a session at nonzero residual scale
- **THEN** persistent lookup and store for that session are refused with an error naming the limitation, and the prompt is computed without disk reuse

#### Scenario: Snapshot while steered
- **WHEN** snapshot save or load is requested at nonzero residual scale
- **THEN** it fails clearly before changing the session's tokens, logits or KV

### Requirement: Runtime no-op evidence
Disabled steering and a zero-direction control at nonzero scale SHALL preserve baseline logits, KV and Engram bitwise under the same schedule. Release evidence SHALL include state comparisons, route coverage and enabled overhead; matching completion text alone SHALL NOT establish bitwise correctness.

#### Scenario: Slow-path control
- **WHEN** a zero vector is used at nonzero residual scale for 65 decoded steps
- **THEN** state and logits match baseline even though the intervention path is exercised

### Requirement: Second residual direction
The V4.1 residual site SHALL accept an optional second per-layer unit direction
(`--dir-steering-file-2`) with its own constant scale (`--dir-steering-residual-2`),
applied as a second in-place weighted fold after the first on every route that applies
the first. It SHALL share the first direction's opt-in gate, disable switch,
persistence refusal and loader validation.

#### Scenario: Applied on every route of the first fold
- **WHEN** a second direction is active
- **THEN** the token-major decode, prefill-batch and decoder-suffix routes each apply
  the second fold immediately after the first

#### Scenario: Second file without the opt-in
- **WHEN** `--dir-steering-file-2` is given and neither `--allow-v41-steering` nor
  `DS4_ALLOW_V41_STEERING` admits steering
- **THEN** the engine refuses to start with the same message as for the first direction

#### Scenario: Zero second scale is the single-direction run
- **WHEN** a second file is given with `--dir-steering-residual-2 0`
- **THEN** the second direction is not loaded and logits, Engram history and KV state
  are bitwise identical to the run with the first direction alone

#### Scenario: Scale without a file
- **WHEN** `--dir-steering-residual-2` is nonzero and no second file is given
- **THEN** the engine refuses to start naming the missing file

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
- **WHEN** `DS4_STEERING_THINK_PHASE` or `DS4_STEERING_THINK_PHASE2` names a phase, or
  a loaded profile declares one for a slot
- **THEN** that slot is gated to the named phase; an unset or unrecognised value means
  both phases

#### Scenario: Both-phase gating is the unchanged path
- **WHEN** neither slot is gated
- **THEN** the session performs no phase tracking and the run matches the ungated run

#### Scenario: Gated sessions do not share a batch
- **WHEN** a decode batch is assembled for sessions whose engine has a gate set
- **THEN** the native batched path is declined and the sessions decode one at a time,
  since one batched forward applies a single scale to every row

### Requirement: Steering profile file
The engine SHALL accept `--steering-profile`, naming one file that carries every slot's
direction matrix, its constant scale and its phase gate. The file SHALL be an
eight-byte magic, a little-endian `uint32` header length, a JSON header declaring the
intervention site, the matrix shape and one or two slots, then one direction matrix per
slot in slot order.

#### Scenario: A profile replaces the option set
- **WHEN** a profile is loaded
- **THEN** the run is identical to the run configured with the equivalent direction
  files, scales and gates passed as individual options

#### Scenario: A bare name resolves, and a wrong one lists the alternatives
- **WHEN** the argument is not a readable path
- **THEN** it is resolved as a profile name in the repository's profile directory, and
  if nothing matches, the engine lists the profiles that exist

### Requirement: Profile admission and validation
A profile SHALL be refused unless its header names the engine's own site and matrix
shape, each slot carries a nonzero scale and a phase of `both`, `think` or `answer`,
and the file's size equals the header plus one matrix per declared slot. Each matrix
SHALL pass the validation a direction file passed on its own receives. A profile SHALL
itself admit steering, and SHALL NOT be combined with the `--dir-steering-*` options.

#### Scenario: A profile is its own opt-in
- **WHEN** a profile is given and no steering opt-in flag or environment variable is set
- **THEN** the engine starts and applies the profile

#### Scenario: Profile and raw options together are refused
- **WHEN** a profile is given together with any `--dir-steering-*` option
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
