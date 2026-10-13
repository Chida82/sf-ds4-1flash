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
