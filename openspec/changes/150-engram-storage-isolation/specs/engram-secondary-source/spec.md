# Spec Delta

## Purpose

Allows users to isolate sparse Engram reads on a second local device through an explicitly selected and content-validated source while retaining the canonical model and exact inference behavior.

## ADDED Requirements

### Requirement: Optional secondary Engram source
The engine SHALL accept `DS4_ENGRAM_REPLICA` as an optional existing-GGUF path for single-box Metal SSD streaming. An absent or empty value SHALL preserve the current canonical-file behavior. Explicit requests in unsupported modes SHALL fail before inference. The option SHALL NOT redirect expert weights or change Engram addressing.

#### Scenario: No secondary source requested
- **WHEN** the option is absent
- **THEN** Engram uses the canonical model with the existing validation behavior

#### Scenario: Unsupported invocation
- **WHEN** the option is nonempty in CPU, TP or nonstreaming mode
- **THEN** initialization fails with an explanatory error rather than silently ignoring it

### Requirement: Exact table and addressing identity
Before secondary Engram use, the engine SHALL validate compatible architecture, table layouts, row counts, bounds and token-map/hash metadata, and establish byte identity of both externally consumed tables against the canonical model. It SHALL use bounded verification memory, retain the admitted file identity, reject a redundant same-inode source, and avoid repeating whole-table verification for each session. The explicit secondary source SHALL NOT weaken validation of the default source.

#### Scenario: Same table shape with different weights
- **WHEN** a supplied GGUF has matching table dimensions but different table bytes
- **THEN** the engine rejects it before inference

#### Scenario: Different token mapping
- **WHEN** table bytes match but token-map or hash metadata differs
- **THEN** admission fails without using the secondary file

#### Scenario: Source path changes
- **WHEN** the admitted pathname is replaced before a later session opens
- **THEN** the session uses the previously validated identity or fails, never silently admitting the replacement

### Requirement: Preserve bounded exact Engram behavior
Secondary-source operation SHALL preserve bitwise row values, token outputs, logits, session history, image masking and save/restore behavior. It SHALL retain bounded row access rather than load the full tables into RAM, and SHALL leave the admitted expert-cache capacity unchanged.

#### Scenario: Continued text generation
- **WHEN** a session continues after prefill using the secondary source
- **THEN** its logits and history match canonical-source execution bit-for-bit

#### Scenario: Rows divided between both sources
- **WHEN** the kept placement reads part of the rows from the admitted secondary source and the rest from the canonical model
- **THEN** every row, logit and history entry matches canonical-only execution bit-for-bit

#### Scenario: Image-masked tokens and restore
- **WHEN** a session containing image-masked positions is saved and restored
- **THEN** secondary-source execution preserves the same Engram masking and continuation state as the canonical source

### Requirement: Safe row failures and teardown
Invalid row requests, invalid encoded values and short reads SHALL retain their existing error semantics. Observed source mutation SHALL invalidate admission or fail the operation rather than return stale cached rows. Cancellation and teardown SHALL settle readers before source handles or writable outputs are released.

#### Scenario: Truncated secondary table
- **WHEN** a read encounters EOF before a complete row
- **THEN** the operation fails and no partial row is treated as valid model data

#### Scenario: Cancellation with reads pending
- **WHEN** inference is cancelled while secondary reads are active
- **THEN** teardown does not free outputs or close the required handles while those readers still use them

### Requirement: Explicit placement evidence and no data migration
The engine SHALL report the Engram source identity and initialization verification cost separately from row-read activity. It SHALL NOT create or modify model replicas, change filesystems, or claim internal space recovery while the full canonical GGUF remains present.

#### Scenario: Secondary-source benchmark
- **WHEN** a run uses external Engram and optionally a separate prefill replica feature
- **THEN** logs identify both effective placements and separate validation cost from inference timing

#### Scenario: Missing external data
- **WHEN** the configured Engram path is missing
- **THEN** initialization fails without copying, downloading or altering canonical model data
