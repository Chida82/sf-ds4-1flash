# Spec Delta

## ADDED Requirements

### Requirement: Uncertain questions can be escalated to bounded thinking
With `sf.escalate {below, think}`, the server SHALL answer every question with
the plain readout and SHALL re-answer, with `860`'s bounded think of `think`
tokens, exactly the questions whose top probability is under `below`.

#### Scenario: One uncertain question of three
- **WHEN** two questions have top probability 1.0 and one has 0.55, with `below` 0.8
- **THEN** only the third is re-answered with thinking and its `sf` entry has `escalated: true` and the plain answer

#### Scenario: Nothing below the threshold
- **WHEN** every top probability is at least `below`
- **THEN** no thinking runs and `usage.output_tokens` is 0

### Requirement: The threshold is chosen from the bench
The bench SHALL report accuracy and latency per threshold, and the suggested
default SHALL be the smallest threshold reaching 90% of the full-thinking
accuracy gain.

#### Scenario: Recorded sweep
- **WHEN** the sweep finishes
- **THEN** `sysone-bench/record.md` holds one row per threshold and the chosen value
