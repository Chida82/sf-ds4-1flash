# Spec Delta

## ADDED Requirements

### Requirement: Isolated question branches ride one layer sweep
`ds4_session_fork_eval` SHALL evaluate an optional state and K branches in
one layer-major pass, each branch starting from the end of the state and
unable to read any row another branch wrote, and SHALL leave the session
valid at the end of the state.

#### Scenario: Each branch equals a lone append
- **WHEN** three branches of 20, 45 and 60 rows are forked after a 1500-token state
- **THEN** each branch's logits are bitwise those of appending that branch alone, as a sweep, to a snapshot of the state

#### Scenario: The session is the state's
- **WHEN** the fork returns
- **THEN** the session's snapshot is bytewise that of a state-only sweep

#### Scenario: Unsupported cases refuse
- **WHEN** the session is steered, tensor-parallel, or holds an image
- **THEN** the call fails and the session is unchanged

### Requirement: The chat prefill path is not edited
The existing sweep function SHALL have no textual change.

#### Scenario: Parity
- **WHEN** the parity oracle and the bitwise harness run on chat kinds
- **THEN** output is identical to the build before this change

### Requirement: The path is kept only if it is at least twice as fast
On a fresh 1500-token state with ten 45-token questions, the request SHALL
be at least 2× faster than `800`'s branches, with accuracy within the
recorded schedule noise.

#### Scenario: Recorded
- **WHEN** the bench finishes
- **THEN** the record holds the latencies for 10 and 30 questions, fresh and cached, against `800` and `840`, and the decision
