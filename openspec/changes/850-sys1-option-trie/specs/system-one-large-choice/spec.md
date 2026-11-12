# Spec Delta

## ADDED Requirements

### Requirement: Choices of 27 to 255 options are answered from one option list
A `choice` with 27-255 options SHALL number its options, list them once, and
score each option by the token path of its numeric id from one shared
prefill, with conditionals renormalized over the legal continuations at each
node. Its probabilities SHALL sum to 1.

#### Scenario: Forty options
- **WHEN** a 40-option choice is asked and the state names option 27
- **THEN** the top is that option and the probabilities sum to 1

#### Scenario: Cost
- **WHEN** a 100-option choice is answered
- **THEN** at most 9 extra single-token evaluations run, and `sf.evaluated_nodes` reports how many

#### Scenario: Over the limit
- **WHEN** a choice has 256 options
- **THEN** the status is 422

### Requirement: Small choices are unchanged
A `choice` with 1-26 options SHALL keep the letter readout.

#### Scenario: Twenty-six options
- **WHEN** a 26-option choice runs before and after this change
- **THEN** its option logits are bitwise equal
