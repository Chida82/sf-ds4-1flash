# Spec Delta

## REMOVED Requirements

### Requirement: V4.1 steering opt-in
**Reason**: Steering on V4.1 is configured only through a profile, and the profile is its own admission. The opt-in existed to admit a raw `--dir-steering-file`, which has no residual-site scale left to apply.
**Migration**: Build a `.sfsteer` profile with `com-steering/make_profile.py` and pass it with `--steering-profile` (CLI, eval) or, after `640`, `--steering-profile-on-request` (server).

### Requirement: Presence-based environment opt-in
**Reason**: `DS4_ALLOW_V41_STEERING` was the environment form of the removed opt-in.
**Migration**: As for the opt-in: pass a profile. The variable is no longer read; `ds4_env.def` reports it as set but never read if it remains in an environment.

### Requirement: Admission-only no-op
**Reason**: It specified the opt-in without a file or with zero scales. Neither configuration exists any more: there is no opt-in, and every profile slot carries a nonzero scale.
**Migration**: None. Unsteered runs are the runs without a profile, and "Runtime no-op evidence" still covers the zero-direction control.

## MODIFIED Requirements

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
- **WHEN** a decode batch is assembled for sessions whose engine has a gate set
- **THEN** the native batched path is declined and the sessions decode one at a time,
  since one batched forward applies a single scale to every row

### Requirement: Steering profile file
The CLI and eval SHALL accept `--steering-profile`, naming one file that carries every slot's
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
