# Spec Delta

## ADDED Requirements

### Requirement: Surveyed techniques carry a recorded decision
`docs/system-one.md` SHALL list, for the techniques found in other System One
projects, whether each is covered by an existing change, discarded with a
reason, or probed here with a result.

#### Scenario: A discarded technique is proposed again
- **WHEN** someone proposes verbalized JSON probabilities
- **THEN** the page already states the reason it was discarded

### Requirement: Rotation averaging is kept only on a measured gain
Averaging rotated option orders SHALL be offered by the server only if
re-asking at most 30% of items gains 2 accuracy points or 0.05 calibrated
NLL.

#### Scenario: No gain
- **WHEN** the full-set analysis shows less
- **THEN** no server option is written and the record holds the table

### Requirement: Chained questions are measured against isolated ones
The bench SHALL compare, per position in the chain and in both question
orders, chained accuracy with isolated accuracy; the chained layout SHALL
remain available only if it stays within 1 point.

#### Scenario: First question
- **WHEN** a request is answered chained
- **THEN** its first question's option logits are bitwise equal to the isolated readout

#### Scenario: Order effect
- **WHEN** chained accuracy falls more than 1 point in either order
- **THEN** the option and its code are removed and the record says why

### Requirement: A graded yes/no readout is measured
The bench SHALL compare a 1-9 rating readout of `noul` with the two-letter
readout on accuracy, NLL and ECE, raw and calibrated.

#### Scenario: Calibration halves
- **WHEN** graded raw ECE is at most half the two-letter ECE with accuracy within 1 point
- **THEN** graded becomes the `noul` readout of a new template version
