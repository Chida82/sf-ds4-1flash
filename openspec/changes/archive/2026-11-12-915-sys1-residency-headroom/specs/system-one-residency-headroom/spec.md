# Spec Delta

## ADDED Requirements

### Requirement: A decision's time is split into compute and read wait
The bench SHALL report, for token-by-token states and for swept states, the
share of a decision's wall time spent in GPU execution, in SSD read wait and
elsewhere, and the predicted resident time.

#### Scenario: Recorded table
- **WHEN** stage 1 finishes
- **THEN** `sysone-bench/record.md` holds one row per run with the three shares and the prediction

### Requirement: The headroom decides the next step
The record SHALL state "go", "modest" or "compute-bound" from the read-wait
share of the swept run, using the thresholds 0.5 and 0.25.

#### Scenario: Compute-bound
- **WHEN** read wait is under 25% of wall time
- **THEN** stage 2 is not run and the record says more machines only add parallel requests
