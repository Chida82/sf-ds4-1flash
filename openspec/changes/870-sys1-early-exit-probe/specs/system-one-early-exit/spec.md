# Spec Delta

## ADDED Requirements

### Requirement: An early exit reads the same fold the last layer would
With `DS4_V41_EXIT_LAYER=L` (1-39) and token-major prefill, the decode step
SHALL run layers 0..L−1, copy that last block's stream weights into the
weights the output head folds with, and read the logits there.

#### Scenario: Unset is unchanged
- **WHEN** the variable is not set
- **THEN** decode logits are bitwise those of the build before this change

#### Scenario: The fold is handed over
- **WHEN** the step exits at L < 40
- **THEN** the head folds the four streams with the split weights of layer L−1, not with the step's initial weights

### Requirement: The cost of a truncated token is measured before its accuracy
The change SHALL first record milliseconds per prefilled token at L = 12, 20,
28 and 40, each in one long-lived process, and SHALL stop when
t(20)/t(40) exceeds 0.75.

#### Scenario: Timing row
- **WHEN** stage 0a finishes
- **THEN** `sysone-bench/record.md` holds the four medians, the two ratios and the gate's outcome

### Requirement: The readout below the last layer is measured, raw and fitted
The bench SHALL record accuracy, agreement with the L = 40 answer and legal
mass at L = 40, 36, 32, 28, 24, 20, 16, 12 and 8, with intervals resampled by
state. When the gate asks for it, three translators SHALL be fitted on
states held out from the test and reported by state and by schema.

#### Scenario: Per-layer table
- **WHEN** stage 0b finishes
- **THEN** the record holds one row per L and the gate's outcome

### Requirement: The experiment ends in a recommendation, not a feature
The change SHALL end with either the probe reverted and a "stop" record, or
the probe kept and a written list of what a session-level exit layer needs.
It SHALL NOT enable an early exit on any production path.

#### Scenario: Stop
- **WHEN** a gate fails
- **THEN** `ds4.c` and `ds4_env.def` are back to their state before the change, and `docs/system-one.md` records the tables

#### Scenario: Follow up
- **WHEN** some layer at or below 32 reaches 95% agreement by state and by schema
- **THEN** the docs name the layer, the translator if any, and the follow-up list, and the owner is asked before any further change
