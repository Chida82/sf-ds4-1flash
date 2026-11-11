# Spec Delta

## Purpose

Defines which routed experts a V4.1 prefill sweep under SSD streaming delivers
to its layer buffers, and what the engine reports about that delivery.

## ADDED Requirements

### Requirement: Selected-expert report of a sweep
With `DS4_METAL_V41_PREFILL_SELECTED_STATS=1`, every layer of a prefill sweep
that runs as one tile and uses the explicit expert buffers SHALL print one
stderr line with the layer, the row count, the number of distinct routed
experts its rows selected, how many of those were not in the decode cache when
the layer's delivery started, and how many of the layer's experts were not in
the cache at that time.

#### Scenario: A 300-row append
- **WHEN** the bench prefills 5000 tokens and then appends 300 with the probe set
- **THEN** stderr holds 40 lines `ds4: V4.1 prefill selected layer=<0..39> rows=300 distinct=<d> distinct_uncached=<du> uncached=<u>`, one per layer, with `d <= 384`, `d <= 1800`, `du <= d` and `du <= u`

#### Scenario: Sweeps outside the report
- **WHEN** the probe is set and a sweep runs as several tiles, or without the explicit expert buffers
- **THEN** that sweep prints no such line

### Requirement: The report does not change the run
The report SHALL NOT change tokens, logits or cache state. Without the
variable the engine SHALL print none of its lines.

#### Scenario: Same output with the probe
- **WHEN** the same bench command runs with and without the probe
- **THEN** the generated tokens and the `--cache-stats` hit and miss counters are equal

#### Scenario: Quiet by default
- **WHEN** the variable is not set
- **THEN** stderr holds no `V4.1 prefill selected` line
