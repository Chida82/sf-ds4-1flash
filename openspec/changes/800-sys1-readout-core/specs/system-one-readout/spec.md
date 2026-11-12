# Spec Delta

## ADDED Requirements

### Requirement: Typed decisions are read from logits without generating
The engine-side module `sf_sysone` SHALL answer `noul`, `choice` (1-26
options) and `score` (1-10 levels) questions about a state by prefilling the
state and the question and reading the next-token logits of the option
symbols. It SHALL NOT sample or decode a token.

#### Scenario: A choice question
- **WHEN** the state "My package arrived broken and I want my money back." is asked the choice {refund_request, shipping_question, praise}
- **THEN** the top option is `refund_request`, the probabilities sum to 1, and the answer carries its legal mass

#### Scenario: One option
- **WHEN** a choice has a single option
- **THEN** its probability is 1 and the session is not evaluated

### Requirement: Questions are isolated
Each question SHALL be evaluated from the same saved state, restored with
`ds4_session_load_snapshot`, so that no question's text or answer can affect
another.

#### Scenario: Bitwise isolation
- **WHEN** a question is asked alone and then as the third of three questions on the same state
- **THEN** its option logits are bitwise equal

#### Scenario: Determinism
- **WHEN** the same request runs twice on the same build
- **THEN** every option logit is bitwise equal

### Requirement: Confidence follows the Jev formulas
`choice` confidence SHALL be `(p_top − 1/n)/(1 − 1/n)`; `score` confidence
SHALL be `max(0, 1 − Σ p_i·|i − m|/MAD)` with m the most likely level and
`MAD = (1/n) Σ |i − (n−1)/2|`; `noul` SHALL report the probability of yes.

#### Scenario: Score example
- **WHEN** a three-level score has probabilities (0, 0.57, 0.43)
- **THEN** its confidence is 0.35 within 0.01

### Requirement: Option symbols are verified single tokens
At open, each symbol SHALL be checked to be one token and to be the token the
tokenizer produces after the answer prefill; a failure SHALL be an error that
names the symbol.

#### Scenario: Symbols on the shipped model
- **WHEN** `sf_sysone_open` runs on the Q2 GGUF
- **THEN** it succeeds for A-Z and 0-9

### Requirement: The engine sources are untouched
The module SHALL use only the public `ds4.h` API.

#### Scenario: Chat output unchanged
- **WHEN** `git diff main -- ds4.c ds4_metal.m ds4.h` runs on this change
- **THEN** it prints nothing
