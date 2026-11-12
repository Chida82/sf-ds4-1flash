# Spec Delta

## ADDED Requirements

### Requirement: The indexer's scores at a decision are measured as evidence
With `DS4_V41_INDEX_PROBE=<file>`, after a sync whose last row ran token by
token on a context of 2 to 16384 tokens, the engine SHALL append the last
index layer's score of every token. The bench SHALL report, on states with
one planted fact, how often the fact's line ranks in the top 5 by score, raw
and after subtracting a content-free question's scores.

#### Scenario: Unset is unchanged
- **WHEN** the variable is not set
- **THEN** decode logits are bitwise those of the build before this change

#### Scenario: One record per decision
- **WHEN** a decision on a 3000-token state runs with the probe
- **THEN** the file gains one record whose count equals the request's total tokens

#### Scenario: Recorded result
- **WHEN** the run finishes
- **THEN** `sysone-bench/record.md` holds recall@5 and MRR, raw and prior-subtracted, over all fact items and over correctly answered ones, and the gate's outcome

### Requirement: State tokens can be mapped back to the state text
With `sf.debug`, a decision response SHALL carry the index of the first state
token and the byte length of each state token's text.

#### Scenario: Lengths cover the state
- **WHEN** the lengths are summed
- **THEN** the sum equals the UTF-8 length of the state text

### Requirement: The probe ends in a recommendation, not a feature
The change SHALL end with the engine edits reverted and a "stop" record, or
with the probe kept and a written follow-up list. It SHALL NOT add evidence
fields, a locate type or a rerank endpoint.

#### Scenario: Stop
- **WHEN** recall@5 stays under 70% at layer 36 and at layer 20
- **THEN** `ds4.c` and `ds4_env.def` are back to their state before the change
