# system-one-state-cache Specification

## Purpose
Keep prefilled states across `/v1/systemone` requests and preserve the chat session around a decision, so a repeated or extended state does not pay its prefill again.

## Requirements

### Requirement: A repeated state is not prefilled again
The server SHALL keep up to `--sysone-state-cache` state snapshots (default 4)
within `--sysone-state-cache-mb` (default 2048), keyed by the state prefix
tokens compared in full. A request whose state prefix equals a cached one
SHALL restore it instead of prefilling, and its answers SHALL be bitwise those
of the request that created the entry.

#### Scenario: Same state, new question
- **WHEN** two requests carry the same 600-token state and different questions
- **THEN** the second reports `state_cache` `hit` and a state prefill under 100 ms

#### Scenario: Cache disabled
- **WHEN** the server runs with `--sysone-state-cache 0`
- **THEN** every request reports `miss` and answers equal those of `810`

### Requirement: A state that grows by appending prefills only the new part
A request whose state prefix extends a cached one SHALL restore the longest
such entry and prefill the remaining tokens. Its answers MAY differ in bits
from a from-scratch prefill of the same state, because the prefill schedule
differs.

#### Scenario: Extended transcript
- **WHEN** a state is sent, then the same state with 100 tokens appended
- **THEN** the second reports `extend` and prefills about 100 tokens

### Requirement: A decision does not cost the chat its live prefix
When the slot's session holds a valid, unsteered checkpoint within the byte
budget, the server SHALL save it before a decision and restore it afterwards.

#### Scenario: Decision between two chat turns
- **WHEN** a chat turn, a decision, and the next chat turn of the same conversation are sent
- **THEN** the second chat turn prefills only its new tokens

#### Scenario: Steered chat session
- **WHEN** the slot's session is steered
- **THEN** the decision still succeeds and the next chat turn prefills from its usual sources
