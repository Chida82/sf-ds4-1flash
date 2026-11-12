# Spec Delta

## ADDED Requirements

### Requirement: A conversation can be the state of a decision
With `"sf":{"state":"messages"}` and `state` an array of `system`, `user` and
`assistant` messages with string content, the server SHALL render the
messages with the chat template, ask each question as a next user turn with
thinking off, and answer each from the same saved state.

#### Scenario: Unsupported message
- **WHEN** a message has a tool role or non-string content
- **THEN** the status is 422 and names the field

#### Scenario: Isolation holds
- **WHEN** a live-state request has three questions and is sent twice
- **THEN** every option logit is bitwise equal between the two

### Requirement: The live session is reused
When the slot's live session is a token prefix of the rendered conversation,
only the remaining tokens SHALL be evaluated, and the chat's state SHALL be
restored after the decision.

#### Scenario: Decision right after a chat turn
- **WHEN** a chat turn with thinking off is followed by a live-state decision on that conversation
- **THEN** `sf.reused_tokens` is at least the chat request's prompt tokens and the state prefill takes under 0.5 s

#### Scenario: Chat continues
- **WHEN** the conversation's next chat turn follows the decision
- **THEN** it prefills only its new tokens

### Requirement: The feature is kept only if it is faster
It SHALL be kept only when the median latency of a live-state decision is at
most one third of the same decision with the conversation sent as a text
state.

#### Scenario: Recorded
- **WHEN** the bench scenario finishes
- **THEN** `sysone-bench/record.md` holds both medians and the decision
