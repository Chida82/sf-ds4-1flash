# Spec Delta

## ADDED Requirements

### Requirement: The strength of the prior correction is fitted, not assumed
The bench SHALL fit, per question type and on states held out from the test,
the factor β in `softmax((z − β·c(z0))/T0)` for a content-free prior and for
a batch prior, and SHALL report NLL, accuracy and rotation flip rate against
β = 0 with paired state-level intervals.

#### Scenario: Recorded table
- **WHEN** the fit finishes
- **THEN** `sysone-bench/record.md` holds, per layout and type, the chosen β for both priors, the three differences with intervals, and the decision

### Requirement: The factor is applied only if it helps
`prior_beta` SHALL be written to the calibration file only when held-out NLL
improves with an interval excluding zero, or the flip rate falls by a third,
without accuracy falling by more than one point.

#### Scenario: No gain
- **WHEN** the best β gains under 0.01 nats and the flip rate does not fall
- **THEN** no code changes and the record holds a rejected row

#### Scenario: Applied
- **WHEN** the file carries `prior_beta` and a `schema_first` request asks for prior correction
- **THEN** the cached prior is scaled by that factor, and a factor of 1 reproduces the previous answers bitwise
