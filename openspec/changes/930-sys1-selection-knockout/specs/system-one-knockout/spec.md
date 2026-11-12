# Spec Delta

## ADDED Requirements

### Requirement: Masking a span from the indexer's candidates is a test-only probe
Through a test hook, a session SHALL accept a row mask that removes blocks
from the candidates of every index layer on the token path, with the
attended count reduced accordingly, and SHALL refuse it above 16384 rows,
under tensor parallelism, before a sweep, and for any save of the session.

#### Scenario: Neutral mask
- **WHEN** the mask allows every row
- **THEN** logits are bitwise those without a mask

#### Scenario: Masked rows are never selected
- **WHEN** fewer than 512 rows remain unmasked
- **THEN** the selection holds only unmasked ids, on both top-k variants

### Requirement: The probe's value is decided by a gold-versus-random comparison
The record SHALL state whether masking the span that carries a planted fact
lowers the correct option's log-odds more than masking random spans of equal
size.

#### Scenario: Recorded either way
- **WHEN** the run finishes
- **THEN** the record and `docs/MODEL_KNOWLEDGE.md` state the result, and the engine edits are reverted unless the owner keeps them
