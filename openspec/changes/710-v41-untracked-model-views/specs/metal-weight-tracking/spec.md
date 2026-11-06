# Spec Delta

## Purpose

Defines which Metal buffers holding model weights are created without hazard
tracking, the condition that makes that safe, and the switch that restores
tracking.

## ADDED Requirements

### Requirement: Read-only weights are untracked by default
The Metal buffers that wrap the model file (model views and exact-range views)
and the narrow decode copies SHALL be created with hazard tracking off, unless
`DS4_METAL_MODEL_TRACKED=1` is set at engine open. Buffers the GPU writes,
including the expert cache slabs and the explicit prefill expert buffers,
SHALL stay tracked.

#### Scenario: Default open
- **WHEN** an engine opens without `DS4_METAL_MODEL_TRACKED`
- **THEN** the model views and the narrow copies are untracked, and the expert cache slabs are tracked

#### Scenario: Tracking restored
- **WHEN** an engine opens with `DS4_METAL_MODEL_TRACKED=1`
- **THEN** every buffer is created tracked, as before this change

### Requirement: Untracked weights are never written by the GPU
No kernel SHALL take an untracked weight buffer as an output. The narrow
copies SHALL be filled by the CPU before their first GPU use and never
written again.

#### Scenario: Copy fill order
- **WHEN** the graph allocates the narrow copies
- **THEN** their contents are written by the CPU before any command buffer reads them

### Requirement: Same output with and without tracking
Greedy decode SHALL produce bitwise identical logits with and without
`DS4_METAL_MODEL_TRACKED=1`.

#### Scenario: Two processes
- **WHEN** the same prompt is prefilled and decoded in two processes, one with the switch and one without
- **THEN** the dumped logits are byte-identical
