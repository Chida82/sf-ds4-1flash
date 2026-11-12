# Spec Delta

## ADDED Requirements

### Requirement: Every layer is screened for the answer without an engine edit
A tool on the public `ds4.h` API SHALL record, for each decision, the
teacher's option logits and the 512-value row of each of the 40 layers at
the readout position, taken from a session snapshot whose header it
verifies. An offline fit SHALL report, for every layer, how often
answer-symbol centroids on that row reproduce the teacher's top option, on
states and on schemas held out from the fit.

#### Scenario: Per-layer table
- **WHEN** the capture and the fit have run
- **THEN** `sysone-bench/record.md` holds 40 rows of agreement by state and by schema, the majority baseline, and a verdict for `870`

#### Scenario: Format guard
- **WHEN** a snapshot's header words differ from the expected values
- **THEN** the tool exits naming the first mismatch and writes no record

#### Scenario: No engine edit
- **WHEN** the change is complete
- **THEN** `git diff main -- ds4.c ds4_metal.m ds4.h ds4_server.c` prints nothing

### Requirement: A similarity readout is measured layer by layer
The fit SHALL score each option by the centred cosine between the row at the
end of state and question and the row of the option text encoded alone, for
every layer, and SHALL report agreement with the teacher and accuracy, with
`choice` as the headline and `noul` and `score` apart.

#### Scenario: The CLM question is answered
- **WHEN** the fit finishes
- **THEN** the record states the best layer at or below 24, its agreement, and one of the three verdicts of the design

### Requirement: A failed probe is reported as inconclusive
Because the row is a 512-value view of a 5120-value state, the record SHALL
NOT state that a layer lacks the answer on the basis of a failed probe.

#### Scenario: Wording of a failure
- **WHEN** no layer at or below 32 reaches 60%
- **THEN** the verdict says the view does not carry the symbol, and leaves `870` to the owner
