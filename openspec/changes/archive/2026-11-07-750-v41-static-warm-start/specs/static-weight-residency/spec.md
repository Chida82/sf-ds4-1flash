# Spec Delta

## Purpose
Defines whether the static weights are in memory when a prefill starts under SSD
streaming, so that prefill speed does not depend on the file cache another
process or an earlier request left behind.

## ADDED Requirements

### Requirement: First prefill independent of the inherited file cache
Under SSD streaming, when the static weights stay pageable, the first prefill
of a fresh engine SHALL find them in memory whatever the previous process left
in the file cache. When they are already cached, this SHALL cost under 2% of
the time from engine start to the end of the first prefill.
`DS4_METAL_DISABLE_STREAMING_STATIC_PREFAULT=1` SHALL restore the previous
behaviour.

#### Scenario: Static weights already cached
- **WHEN** the start state is every page of the GGUF dropped (`touch.py evict .`) and every static weight read back, and the bench runs the 2048-token prompt in a fresh process
- **THEN** the time from engine start to the end of the first prefill is within 2% of the same run with the prefault switched off

#### Scenario: Cold start
- **WHEN** the file cache holds none of the model (after `purge` or `touch.py evict .`)
- **THEN** the time from engine start to the end of the first prefill is shorter than without the prefault, and the static weights resident when the prefill starts are within 64 MiB of all of them

#### Scenario: Full file cache
- **WHEN** the static weights were read and then 60 GiB of other file data, so the engine's lock-ahead must evict file pages
- **THEN** the static weights resident when the prefill starts are within 64 MiB of all of them, and the time from engine start to the end of the first prefill is shorter than without the prefault

### Requirement: Prefills in a long-lived process
In one engine process, a prefill that follows a long generation SHALL NOT page
in more than 64 MiB of static weights, with the narrow decode copies on, when no
other process reads files in between.

#### Scenario: New prompt after a long answer
- **WHEN** one process prefills a 2048-token prompt, generates 2000 tokens, then prefills a different 2048-token prompt
- **THEN** the second prefill pages in under 64 MiB of static weights and runs within 2% of the same prefill with the narrow copies off

### Requirement: Output unchanged
The residency measures SHALL NOT change any logits.

#### Scenario: Bitwise with and without the measures
- **WHEN** the bench dumps frontier logits at 2048 and 8192 with the measures on and with their switches set
- **THEN** every dump is byte-identical
