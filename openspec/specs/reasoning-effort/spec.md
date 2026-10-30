# reasoning-effort Specification

## Purpose
Defines how a server request's thinking controls (effort names, numeric levels, thinking switches and model aliases) become V4.1's thinking mode, the effort line in the prompt, and the level reported to the session.

## Requirements

### Requirement: Named effort levels
The server SHALL map each named effort, on every API that accepts one, to a V4.1 thinking level: `none` and `minimal` to no thinking, `low` to 25, `medium` to 50, `high` to 75, `xhigh` to 90 and `max` to 100. An unknown name SHALL be rejected as an invalid request.

#### Scenario: Each name renders its level
- **WHEN** a chat request with thinking enabled sends `reasoning_effort` `low`, `medium`, `high`, `xhigh` or `max`
- **THEN** the rendered prompt carries `Reasoning Effort: 25`, `50`, `75`, `90` or `100` respectively, followed by the template's range text, and opens thinking

#### Scenario: Minimal means no thinking
- **WHEN** a request sends `reasoning_effort` `minimal`
- **THEN** the prompt carries no effort line and closes thinking, exactly as with `none`

#### Scenario: The same table on every API
- **WHEN** the same name is sent as chat-completions `reasoning_effort`, inside `chat_template_kwargs`, as Anthropic `output_config.effort`, or as Responses `reasoning.effort`
- **THEN** each request renders the same prompt

#### Scenario: Unknown name
- **WHEN** a request sends `reasoning_effort` `banana`
- **THEN** the server answers with an invalid-request error and evaluates nothing

### Requirement: Unchanged prompts for existing levels
The names `none`, `high` and `max`, and every numeric level from `"0"` to `"100"`, SHALL render the same prompt bytes as before this change.

#### Scenario: High and max are byte-identical
- **WHEN** a request sends `high`, `max`, or a numeric level
- **THEN** its rendered prompt is byte-identical to the prompt the previous server rendered for the same request

#### Scenario: Numeric zero means no thinking
- **WHEN** a request sends `reasoning_effort` `"0"`
- **THEN** the prompt closes thinking and carries no effort line

### Requirement: Thinking control precedence
An explicit thinking disable SHALL always win. Otherwise an effort meaning no thinking SHALL disable it. Otherwise a model alias SHALL decide, only when no explicit thinking control was sent. Otherwise thinking SHALL run at the effort level, `high` by default.

#### Scenario: Explicit disable beats any effort
- **WHEN** a request sends `thinking: false` (or `{"type":"disabled"}`, or `think: false`) together with `reasoning_effort` `max`
- **THEN** the prompt closes thinking

#### Scenario: A no-thinking effort beats an enabling alias
- **WHEN** a request for model `deepseek-reasoner` sends `reasoning_effort` `minimal`
- **THEN** the prompt closes thinking

#### Scenario: Explicit enable beats a disabling alias
- **WHEN** a request for model `deepseek-chat` sends `thinking: true` and no effort
- **THEN** the prompt opens thinking at level 75

#### Scenario: Defaults
- **WHEN** a request for model `deepseek-v4.1-flash` sends no thinking control and no effort
- **THEN** the prompt opens thinking at level 75

### Requirement: Session level matches the prompt
The level a frontend reports to the session SHALL equal the level the prompt's effort line carries: 75 for the named high level, 100 for max, the number for a numeric level. A mode without an effort line SHALL report the unknown level.

#### Scenario: Max reports 100
- **WHEN** a server request at `max`, or a CLI run after `/think-max`, prepares its session
- **THEN** the session's reasoning level is 100

#### Scenario: High reports 75
- **WHEN** a request at `high`, or with no effort, prepares its session
- **THEN** the session's reasoning level is 75
