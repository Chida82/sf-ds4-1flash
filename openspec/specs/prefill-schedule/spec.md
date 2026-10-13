# prefill-schedule Specification

## Purpose
The V4.1 prefill schedule: how wide sweeps, the decoder suffix and the deferred decoder reconstruct attention inputs from carried state.

## Requirements

### Requirement: Reconstructed rows use their carried state
When the decoder suffix warms or publishes rows one token at a time, each row's attention input SHALL be folded from that row's own carried residual streams and previous-sublayer weights, never from state belonging to another row or to the decode scratch. Under fixed arithmetic (batch MoE and batch attention off) the suffix route SHALL leave the same KV state, Engram history and logits as the plain route for the same tokens.

#### Scenario: Wide prefill with the suffix, fixed arithmetic
- **WHEN** 8192 tokens are prefilled with batch MoE and batch attention off, once with the decoder suffix and once without
- **THEN** every KV window, compressed and index span, the Engram history and the logits are bitwise equal, and a decode step after each stays equal

#### Scenario: Steered reconstruction inherits the contract
- **WHEN** the same comparison runs with a direction active at a nonzero residual scale
- **THEN** it is bitwise equal as well, with the steered-row counter showing the suffix route projecting its reconstructed rows
