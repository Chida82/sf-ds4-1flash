# Spec Delta

## ADDED Requirements

### Requirement: V4.1 steering opt-in
On V4.1, `--dir-steering-file` SHALL be refused at startup with the upstream line,
unless `--allow-v41-steering` (or `DS4_ALLOW_V41_STEERING=1`) is set. The opt-in
SHALL remove only the steering term from the support check; all other unsupported
conditions SHALL still refuse. With no opt-in, or with the opt-in but no steering
file or zero scales, output SHALL stay bitwise identical to a build without this
change.

#### Scenario: Default path still refuses, verbatim
- **WHEN** `--dir-steering-file v.f32` is passed without `--allow-v41-steering`
- **THEN** the engine prints the exact upstream "requires Metal ... steering ... not
  supported" line and exits 1

#### Scenario: Opt-in lifts only the steering term
- **WHEN** `--allow-v41-steering --dir-steering-file v.f32` is passed on single-box
  Metal
- **THEN** the engine starts, and the same command with `--power 50` still refuses on
  the power term

#### Scenario: No-op gate
- **WHEN** `--allow-v41-steering` is set with no steering file
- **THEN** the 65-token decode logits, KV and Engram are bitwise identical to a run
  without the flag
