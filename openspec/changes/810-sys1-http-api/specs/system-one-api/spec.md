# Spec Delta

## ADDED Requirements

### Requirement: The server answers TypeSafe's System One request
`POST /v1/systemone` SHALL accept `{model, state, questions}` with questions
of type `noul`, `choice` (1-26 options) and `score` (1-10 levels), and SHALL
return `{model, answers, usage}` with the answer fields of
`docs/system-one.md` section 2 and `usage.output_tokens` equal to 0.

#### Scenario: Three questions on one state
- **WHEN** a request carries one state and a `noul`, a `choice` and a `score` question
- **THEN** the response has one answer per question under the same names, in request order, each with its `type`, and choice and score probabilities sum to 1

#### Scenario: Structured state
- **WHEN** `state` is a JSON object
- **THEN** it is read as its minified JSON text and the request succeeds

#### Scenario: Any model name
- **WHEN** `model` is `jev-latest`
- **THEN** the request is answered and `model` in the response is the local model id

### Requirement: Errors use the Jev statuses
Validation failures SHALL return 422 with a `detail` list whose entry has
`loc`, `msg` and `type`. A request whose tokens exceed the context SHALL
return 400 with `max_tokens_exceeded`. `box`, `assets` and more than 26
options SHALL return 422.

#### Scenario: Missing criteria
- **WHEN** a `choice` question has no `criteria`
- **THEN** the status is 422 and `detail[0].loc` ends with the question name and `criteria`

#### Scenario: Over the context
- **WHEN** the state alone is longer than the server's context
- **THEN** the status is 400 and the body contains `max_tokens_exceeded`

### Requirement: Extensions stay out of the standard shape
The response SHALL contain an `sf` object only when the request contained one.

#### Scenario: Plain Jev client
- **WHEN** a request has no `sf` key
- **THEN** the response's top-level keys are exactly `model`, `answers`, `usage`

### Requirement: A decision does not change chat answers
Chat endpoints SHALL give the same output before and after a decision.

#### Scenario: Chat, decision, chat
- **WHEN** the same chat completion at temperature 0 is sent before and after a decision
- **THEN** both chat answers are equal

### Requirement: Models are listed in both shapes
`GET /v1/models` SHALL carry the OpenAI `data` array and Jev's `models` array.

#### Scenario: Jev client lists models
- **WHEN** a client reads `models[0].name`
- **THEN** it is an id the server accepts
