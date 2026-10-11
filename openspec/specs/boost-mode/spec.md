# boost-mode Specification

## Purpose
Defines what `--boost` needs from the machine (the fanboost fan daemon) and how the engine tells the user when that need is not met, so that a boosted run never silently runs on the stock fan curve.

## Requirements

### Requirement: Boost refuses to start without fanboost
When `--boost` is given, the engine SHALL check fanboost before it loads the model. If fanboost is not installed, the engine SHALL print one line naming the missing program, the install command `./fanboost/install.sh` and the option to run without `--boost`, and SHALL exit with a non-zero status.

#### Scenario: fanboost not installed
- **WHEN** the CLI, server or bench starts with `--boost` on a machine without `/usr/local/bin/fanboost`
- **THEN** stderr says fanboost is not installed and how to install it, and the process exits with an error before loading the model

### Requirement: Boost refuses to start when the fanboost daemon is down
When fanboost is installed but its daemon is not running, the engine SHALL print one line saying so, with the reinstall command and the option to run without `--boost`, and SHALL exit with a non-zero status.

#### Scenario: Daemon not running
- **WHEN** the engine starts with `--boost` and `fanboost check` reports the daemon is not running
- **THEN** stderr says the fanboost daemon is not running and how to fix it, and the process exits with an error

### Requirement: The engine asks fanboost through its commands only
The engine SHALL learn fanboost's state only from the exit status of fanboost commands, and SHALL NOT read fanboost's files, notifications or printed output.

#### Scenario: fanboost changes its protocol
- **WHEN** fanboost changes how requests reach its daemon but keeps `fanboost check` and `fanboost max`
- **THEN** `--boost` keeps working without any change to the engine

### Requirement: Losing fanboost during a run is reported once
If a `fanboost max` request fails after the engine has started, the engine SHALL print one warning and SHALL keep running.

#### Scenario: fanboost uninstalled while a server runs
- **WHEN** fanboost is removed while a server started with `--boost` is generating
- **THEN** stderr shows one warning that fan requests fail, and generation continues

### Requirement: Without boost nothing changes
Without `--boost`, the engine SHALL NOT run any fanboost command and SHALL start whether or not fanboost is installed.

#### Scenario: Plain run on a machine without fanboost
- **WHEN** the engine starts without `--boost` on a machine without fanboost
- **THEN** it starts as before and prints nothing about fanboost
