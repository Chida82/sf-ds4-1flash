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

### Requirement: Short appends under SSD streaming run as one layer sweep
On a single box under SSD streaming, once a session holds context, an append
of at least the warm minimum SHALL prefill as layer sweeps instead of token by
token, with the warm minimum set at the measured break-even between the two
paths. Resident and tensor-parallel sessions SHALL keep upstream's schedule.
`DS4_METAL_V41_WARM_APPEND_MIN=<rows>` SHALL set the warm minimum (1-2048);
`1024` SHALL restore upstream's schedule for every append, and its logits SHALL
be bitwise those of the build before this change.

#### Scenario: Chat turn after a 2K context
- **WHEN** a bench session with `80GB` prefills 2048 tokens and then appends 256 to 1000 tokens, with 16 decoded tokens after each
- **THEN** each append's time to first token is below the token-major time of the same append, and a 1000-token append takes under a third of it

#### Scenario: Chat turn after an 8K context
- **WHEN** the same appends follow an 8192-token context
- **THEN** the same holds

#### Scenario: Upstream's schedule on request
- **WHEN** the bench runs with `DS4_METAL_V41_WARM_APPEND_MIN=1024` on this change and without it on the build before
- **THEN** the frontier logits are bitwise equal

#### Scenario: No loss elsewhere
- **WHEN** the harness runs `decode`, `cold` and `append` A/B against the build before this change, accepting the output change
- **THEN** `append +300` gains and no other headline loses beyond its noise
