# Spec Delta

## Purpose

Lets decode read missing routed experts from both local drives when a content-validated replica of the model is admitted, without changing output or the expert cache.

## ADDED Requirements

### Requirement: Decode misses use the admitted replica only for validated bytes
When a replica is admitted for single-box Metal SSD streaming, the engine SHALL read only those bytes of a missing routed expert from the replica that engine-open validation compared with the model; every other byte SHALL come from the model. Without an admitted replica, decode SHALL read only from the model.

#### Scenario: No replica
- **WHEN** no replica is configured
- **THEN** decode expert misses read only the model file

#### Scenario: Replica admitted
- **WHEN** a decode token misses an expert and a replica is admitted
- **THEN** bytes inside validated ranges may come from the replica, and all other bytes come from the model

### Requirement: Identical output and cache budget
Decode with replica reads or prefetch SHALL produce bit-identical logits, tokens and session state, and SHALL keep the configured expert-cache budget. Placement alone SHALL NOT change cache hits, misses or evictions. Prefetch may change them, and SHALL report them.

#### Scenario: Same prompt and cache size
- **WHEN** the same prompt is decoded with and without an admitted replica, and without prefetch
- **THEN** logits, tokens, KV state and cache statistics match exactly

#### Scenario: Prefetch enabled
- **WHEN** route-prediction prefetch is active
- **THEN** logits, tokens and KV state match the run without it; staging memory is bounded and reported, and no expert enters the cache unless it was actually selected

### Requirement: Safe failure during decode
A replica read error, a short read, or a replica changed after it was validated SHALL fail the decode step with an error that names the replica. No partially filled expert slot SHALL ever be published as valid, and no reader SHALL still be writing to a slot when that slot is reused or freed.

#### Scenario: Replica read fails
- **WHEN** a replica read returns an error or ends early during a decode miss
- **THEN** the step fails, the slot stays invalid, and the error names the replica

#### Scenario: Replica changed after validation
- **WHEN** the replica's size or modification time differs from the values recorded at validation
- **THEN** the next decode miss that would read it fails instead of reading unvalidated bytes
