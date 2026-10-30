# Spec Delta

## MODIFIED Requirements

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
