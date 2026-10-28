# Spec Delta

## ADDED Requirements

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
