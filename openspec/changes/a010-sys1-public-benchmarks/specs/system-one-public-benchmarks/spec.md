# Spec Delta

## ADDED Requirements

### Requirement: Public benchmarks are run in full with their published scores beside
The bench SHALL run the full typed-decisions set, the JevBench public items
and the jevify suites in plain-readout, calibrated and thinking modes, and
SHALL record our scores with intervals beside each published score and its
source.

#### Scenario: Recorded table
- **WHEN** the runs finish
- **THEN** `sysone-bench/record.md` has one row per set and mode, the published scores with URLs, and the count and reason of skipped items

#### Scenario: Licence not found
- **WHEN** a set's licence cannot be established
- **THEN** it is not run and the record says so

### Requirement: The record states whether quality justifies the model
The record SHALL classify each set as ahead, level or behind the best
published training-free stock-model score, using the interval rule of the
design, and SHALL state one overall line.

#### Scenario: Level everywhere
- **WHEN** every set is level
- **THEN** the overall line is "no quality advantage in plain readout" and the thinking figure follows

### Requirement: Calibration is never fitted on scored items
Calibrated scores SHALL be computed on items disjoint from those the
temperature was fitted on.

#### Scenario: Held-out half
- **WHEN** a set is scored calibrated
- **THEN** only odd-hash items are scored, with a temperature fitted on even-hash items
