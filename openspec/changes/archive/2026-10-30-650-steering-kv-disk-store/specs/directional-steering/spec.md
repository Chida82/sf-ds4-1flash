# Spec Delta

## MODIFIED Requirements

### Requirement: Steering and persistent state
While a session's steering is on, automatic persistent KV reuse and explicit snapshot save/load SHALL be refused with a clear error before any session mutation, unless the frontend has declared for that session that it keeps steered persistent state apart, bound to the profile's identity. Sessions with steering off, and sessions of an engine without a profile, SHALL keep existing persistent-state behavior. A steered session SHALL NOT read, rewrite or delete cache files outside the store its frontend reserves for it.

#### Scenario: Steered session with a KV root
- **WHEN** a server with a configured KV root runs a session with steering on
- **THEN** that session's persistent lookup, load and store use only the server's steering store, bound to the loaded profile, and never the root

#### Scenario: Snapshot while steered
- **WHEN** snapshot save or load is requested on a session with steering on whose frontend has made no such declaration, including while a gated slot is at zero for the current token
- **THEN** it fails clearly before changing the session's tokens, logits or KV
