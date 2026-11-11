# Spec Delta

## Purpose

Defines which routed experts a V4.1 prefill sweep under SSD streaming delivers
to its layer buffers, and what the engine reports about that delivery.

## ADDED Requirements

### Requirement: Short sweeps deliver only the selected experts
On a single box under SSD streaming, a prefill sweep that runs as one tile,
uses the explicit expert buffers and has at most the selective limit of rows
SHALL deliver to each layer's buffer only the routed experts that at least one
of its rows selected. Every other sweep SHALL deliver whole layers as before.

#### Scenario: A 300-row append reads less
- **WHEN** the bench prefills 5000 tokens, generates, and appends 300 tokens, with the prefill profile on
- **THEN** the per-layer profile lines of the append report fewer GiB from RAM and from the model than the same run with the limit at `0`

#### Scenario: A long sweep is untouched
- **WHEN** a sweep has more rows than the limit, or runs as several tiles
- **THEN** its profile lines report the same GiB from RAM and from the model as with the limit at `0`

### Requirement: Selective delivery keeps the output bitwise
Selective delivery SHALL NOT change any bit of the session: KV state, Engram
history and logits after the sweep, and after decode steps that follow it,
SHALL equal those of whole-layer delivery.

#### Scenario: Appends against whole-layer delivery
- **WHEN** one session prefills 2048 tokens, appends 300, decodes 64 tokens, appends 512 and appends 1000 with the limit at `0`, and another does the same with the default limit
- **THEN** state spans, Engram history and logits are bitwise equal after every append and after the decode steps

#### Scenario: Undelivered experts are never read
- **WHEN** the same sequence runs with `DS4_METAL_V41_SELECTIVE_SWEEP_POISON=1`
- **THEN** the results are bitwise equal to whole-layer delivery

#### Scenario: Harness correctness gate
- **WHEN** the harness runs `append`, `short`, `decode` and `cold-2500` A/B with `--bitwise` against the build before this change
- **THEN** the correctness gate passes

### Requirement: The selective limit is a switch
`DS4_METAL_V41_SELECTIVE_SWEEP_MAX=<rows>` SHALL set the largest sweep that
uses selective delivery (0-2047). `0` SHALL restore whole-layer delivery for
every sweep, with logits bitwise those of the build before this change.

#### Scenario: Off on request
- **WHEN** the bench runs with `DS4_METAL_V41_SELECTIVE_SWEEP_MAX=0` on this change and without it on the build before
- **THEN** the frontier logits are bitwise equal and the profile lines report the same GiB per layer within rounding

### Requirement: Selective delivery pays for itself
At the default limit, a sweep that uses selective delivery SHALL NOT be slower
than whole-layer delivery of the same sweep, and no other harness headline
SHALL lose.

#### Scenario: Short appends gain
- **WHEN** the harness runs `append,short,decode,cold-2500` A/B against the build before this change
- **THEN** the pooled 95% interval of `append +300` lies above zero and no other headline's interval lies wholly below zero
