# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Steering and persistent state
While a session's steering is on, automatic persistent KV reuse and explicit snapshot save/load SHALL be refused with a clear error before any session mutation. Sessions with steering off, and sessions of an engine without a profile, SHALL keep existing persistent-state behavior. A steered session SHALL NOT read, rewrite or delete existing cache files. A steering identity descriptor is not required by this change.

#### Scenario: Steered session with a KV root
- **WHEN** a server with a configured KV root starts a session with steering on
- **THEN** persistent lookup and store for that session are refused with an error naming the limitation, and the prompt is computed without disk reuse

#### Scenario: Snapshot while steered
- **WHEN** snapshot save or load is requested on a session with steering on, including while a gated slot is at zero for the current token
- **THEN** it fails clearly before changing the session's tokens, logits or KV
