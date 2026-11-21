# Spec Delta

## ADDED Requirements

### Requirement: Branch phases are timed
`sf_sysone_decide` SHALL report the state prefill, snapshot save, each restore
and each suffix evaluation in milliseconds, and the server SHALL return them
in the `sf` object.

#### Scenario: Three questions with sf
- **WHEN** a request with `"sf":{}` asks three questions
- **THEN** the `sf` object has `prefill_ms`, `save_ms`, and per question `restore_ms` (0 for the first) and `eval_ms`

### Requirement: Timing does not change answers
Answers SHALL be bitwise equal whether timing is requested or not.

#### Scenario: Timing on and off
- **WHEN** the same request runs with `timing` NULL and non-NULL
- **THEN** every option logit is bitwise equal

### Requirement: The branch cost is recorded with a decision
`docs/system-one.md` SHALL hold the measured medians and the outcome of the
decision rules in the design.

#### Scenario: Overhead above the budget
- **WHEN** save plus restores exceed 30% of the question phase
- **THEN** a follow-up change names the slow call
