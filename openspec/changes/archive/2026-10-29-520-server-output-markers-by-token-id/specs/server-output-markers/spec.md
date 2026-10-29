# Spec Delta

## ADDED Requirements

### Requirement: Output markers are recognized by token id
When the server parses a response it generated, a reasoning boundary, a tool-call start or end, or an end of sentence SHALL be recognized only where the model emitted that marker's control token. This holds for streaming and non-streaming responses on every endpoint.

#### Scenario: Reasoning that quotes the closing tag
- **WHEN** the model, while reasoning, writes the characters `</think>` with ordinary tokens and later emits the closing control token
- **THEN** the reasoning field contains the quoted characters, and the answer starts after the control token

#### Scenario: Answer that quotes a tool-call tag
- **WHEN** the model's answer spells the DSML tool-call opening tag with ordinary tokens
- **THEN** the response reports no tool call, and the tag's characters appear in the content

### Requirement: Literal spellings stay text
A marker string that the model spelled with ordinary tokens SHALL reach the client unchanged, in the field where it was generated. It SHALL NOT change the sampling mode.

#### Scenario: Sampling mode unaffected
- **WHEN** the model spells a tool-call tag with ordinary tokens during a sampled answer
- **THEN** the following tokens are sampled with the request's settings, not with greedy tool syntax

### Requirement: Ordinary responses are unchanged
For a generation in which every marker came from its control token, the response body SHALL be byte-identical to the previous build's.

#### Scenario: Greedy request with reasoning and a tool call
- **WHEN** the same greedy request that reasons and then calls a tool is sent before and after this change
- **THEN** the tokens and the response body are identical
