# Spec Delta

## ADDED Requirements

### Requirement: Public benchmarks are run in full with their published scores beside
The bench SHALL run the full typed-decisions set, the JevBench public items
and the jevify suites in plain-readout and calibrated modes, and in thinking
mode at medium effort on the sets the design names, and SHALL record our
scores with intervals beside the four fixed references (Jev 1.13.0, CLM-8B,
the best Qwen-derived system, Rizzo Flow) and the best other non-DeepSeek
figure, each with its source.

#### Scenario: Recorded table
- **WHEN** the runs finish
- **THEN** `sysone-bench/record.md` has one row per set and mode, the published scores with URLs, and the count and reason of skipped items

#### Scenario: Reference without a figure
- **WHEN** a reference has published nothing on a set
- **THEN** its cell is empty and no other system takes its place

#### Scenario: Licence not found
- **WHEN** a set's licence cannot be established
- **THEN** it is not run and the record says so

### Requirement: The record states whether quality justifies the model
The record SHALL classify each set as ahead, level or behind each reference
with a figure, using the interval rule of the design (the sign test where the
reference has per-item outcomes), and SHALL state one overall line.

#### Scenario: Level everywhere
- **WHEN** every set is level
- **THEN** the overall line is "no quality advantage in plain readout" and the thinking figure follows

### Requirement: Calibration is never fitted on scored items
Calibrated scores SHALL be computed on items disjoint from those the
temperature was fitted on.

#### Scenario: Held-out half
- **WHEN** a set is scored calibrated
- **THEN** only odd-hash items are scored, with a temperature fitted on even-hash items

### Requirement: Thinking answers keep the reasoning out of the answer
In thinking mode the answer SHALL be read from the reply's content only, never
from the reasoning, and the record SHALL report the completion tokens per
decision.

#### Scenario: Reasoning names an option
- **WHEN** the reasoning mentions several option symbols and the content is `C`
- **THEN** the answer is option C

### Requirement: Quantization is checked against the production model
The record SHALL compare our thinking answers on the jevbench public items
with the same model's production API run, item by item, and SHALL state
whether a gap is measurable.

#### Scenario: Gap above two points
- **WHEN** the API run is more than 2 points ahead with p < 0.05
- **THEN** the disagreeing items are rerun at high effort and the record says whether effort or weights explain the gap
