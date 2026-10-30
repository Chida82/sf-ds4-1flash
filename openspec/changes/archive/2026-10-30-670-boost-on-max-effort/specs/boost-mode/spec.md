# Spec Delta

## ADDED Requirements

### Requirement: Server boost on max effort
With `--boost-on-max-effort`, the server SHALL keep boost off while no request is generating at effort level 100, and SHALL turn it on while at least one such request is generating. Level 100 is the request's thinking mode after the thinking-control precedence: effort `max` on any API, or the numeric level `"100"`. Boost SHALL have the same two effects as `--boost`: the fan hint and the decode keep-alive.

#### Scenario: A max request boosts while it runs
- **WHEN** a server started with `--boost-on-max-effort` receives a chat request with `reasoning_effort` `max` and thinking enabled
- **THEN** boost is on from the start of that request's generation until it ends, and off afterwards

#### Scenario: Lower levels do not boost
- **WHEN** the same server receives requests with effort `xhigh`, `high`, a numeric level below 100, or no effort
- **THEN** boost stays off and no `fanboost max` command runs

#### Scenario: Disabled thinking does not boost
- **WHEN** a request sends `reasoning_effort` `max` together with an explicit thinking disable
- **THEN** boost stays off

#### Scenario: Every API's max boosts
- **WHEN** max effort arrives as Anthropic `output_config.effort`, Responses `reasoning.effort`, or inside `chat_template_kwargs`
- **THEN** boost is on while that request generates

### Requirement: Boost while any max request is active
With batched or concurrent requests, boost SHALL stay on as long as at least one level-100 request is generating, and SHALL turn off only when the last one ends.

#### Scenario: Overlapping max requests
- **WHEN** two max requests overlap and the first one ends while the second is still generating
- **THEN** boost stays on until the second one ends

#### Scenario: A max request among plain ones
- **WHEN** a max request is generating alongside plain requests in the same decode batch
- **THEN** boost is on for the whole machine while the max request runs

### Requirement: Boost on max effort checks fanboost at startup
With `--boost-on-max-effort`, the server SHALL check fanboost before it loads the model, with the same refusals as `--boost` (fanboost not installed, daemon not running), naming `--boost-on-max-effort` in the message. After a passing check it SHALL NOT run `fanboost max` until a level-100 request generates.

#### Scenario: Daemon down at startup
- **WHEN** the server starts with `--boost-on-max-effort` and `fanboost check` reports the daemon is not running
- **THEN** stderr says so, naming `--boost-on-max-effort`, and the process exits with an error before loading the model

#### Scenario: Idle after startup
- **WHEN** the server starts with `--boost-on-max-effort`, fanboost is running, and no request arrives
- **THEN** no `fanboost max` command runs

### Requirement: Boost options are exclusive
The server SHALL refuse to start when both `--boost` and `--boost-on-max-effort` are given, with an error naming both options.

#### Scenario: Both flags
- **WHEN** the server is started with `--boost --boost-on-max-effort`
- **THEN** it exits with an error before loading the model

### Requirement: Boost transitions are logged
The server SHALL log one line when boost turns on, naming the request that turned it on, and one line when it turns off.

#### Scenario: One max request
- **WHEN** a single max request runs on an otherwise idle server with `--boost-on-max-effort`
- **THEN** the log shows exactly one boost-on line and one boost-off line for it

### Requirement: Boost on max effort keeps output identical
Turning boost on or off between or during requests SHALL NOT change any generated token.

#### Scenario: Same max request with and without the option
- **WHEN** the same greedy max-effort request is sent to a server with `--boost-on-max-effort` and to one without it
- **THEN** both return identical tokens

## MODIFIED Requirements

### Requirement: Without boost nothing changes
Without `--boost` or `--boost-on-max-effort`, the engine SHALL NOT run any fanboost command and SHALL start whether or not fanboost is installed.

#### Scenario: Plain run on a machine without fanboost
- **WHEN** the engine starts without `--boost` or `--boost-on-max-effort` on a machine without fanboost
- **THEN** it starts as before and prints nothing about fanboost
