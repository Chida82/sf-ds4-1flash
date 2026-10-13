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
