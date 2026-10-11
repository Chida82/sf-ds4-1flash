# env-switches Specification

## Purpose
Defines how every `DS4_*` environment switch the code reads is classified and described, and what the engine tells the user at startup about switches that are set.

## Requirements

### Requirement: Every switch the code reads is classified
The repository SHALL hold one classification entry for each `DS4_*` name the sources read. Each entry SHALL give the name, a category (`operational`, `tuning`, `disable`, `enable`, `probe` or `test`), the normal-use state (`unset` or `any`) and a one-line description of what the variable does.

#### Scenario: Description available
- **WHEN** a user or an agent looks up a `DS4_*` name in the classification
- **THEN** its category, normal-use state and description are found on one line

### Requirement: The test suite rejects unclassified switches
`make test` SHALL fail when the sources read a `DS4_*` name that the classification does not list, and SHALL name each such variable. It SHALL also name each classified variable that the sources no longer read.

#### Scenario: Upstream adds a switch
- **WHEN** a sync brings code that reads a new `DS4_*` variable and the classification is not updated
- **THEN** `make test` fails and prints the new variable's name

#### Scenario: A switch is removed
- **WHEN** the sources stop reading a classified variable
- **THEN** `make test` names it as a classification entry to remove

### Requirement: Startup reports switches out of their normal state
At engine open, the CLI, server, bench and eval SHALL print to stderr each set `DS4_*` variable whose normal-use state is `unset`, with its value, category and description. Variables at their normal-use state SHALL NOT be printed. With nothing to report, nothing SHALL be printed.

#### Scenario: Clean terminal
- **WHEN** an engine opens with no `DS4_*` variable set, or only variables whose normal-use state is `any`
- **THEN** the startup output contains no environment report

#### Scenario: A probe left exported
- **WHEN** an engine opens with a `probe` variable set
- **THEN** stderr shows that variable, its value, the category `probe` and its description

### Requirement: Startup reports switches this build does not read
At engine open, the engine SHALL print each set `DS4_*` variable that this build never reads, marked as unknown to this build.

#### Scenario: Leftover from a removed feature
- **WHEN** an engine opens with a `DS4_*` variable set that no source of this build reads
- **THEN** stderr shows that variable marked as not read by this build
