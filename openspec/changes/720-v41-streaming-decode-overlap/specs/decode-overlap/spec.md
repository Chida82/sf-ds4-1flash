# Spec Delta

## Purpose

Defines the V4.1 decode work that may be moved off the streaming critical
path, the pre-screen that admits a candidate, and the exactness and switches
every admitted candidate keeps.

## ADDED Requirements

### Requirement: Candidates are pre-screened before a port
A candidate SHALL be ported only after a micro-bench on this machine shows a
per-token saving the harness can resolve. A candidate that fails the screen
SHALL be recorded as a rejected idea with its figure.

#### Scenario: Saving too small
- **WHEN** the micro-bench of a candidate shows a saving below the harness resolution
- **THEN** no code is ported and perf-record gains a rejected-ideas row with the measured saving

### Requirement: Shared RoPE table is exact
If ported, the per-token RoPE table SHALL leave every decoded logit bitwise
identical to the per-layer RoPE path, including on exact FP4 midpoints of the
index query.

#### Scenario: Switch test
- **WHEN** `make test-deepseek41-decode-switch` runs with the table's switch
- **THEN** every decoded token matches

### Requirement: Overlapped hyper-connection weights are exact
If ported, the hyper-connection weights computed beside the projections or in
the router readback window SHALL produce the same bits as the in-order
computation, and SHALL not overwrite any scratch a pending expert miss still
reads.

#### Scenario: Switch test under misses
- **WHEN** the decode switch test runs in streaming with a cache small enough that tokens miss
- **THEN** every decoded token matches with and without the switch
