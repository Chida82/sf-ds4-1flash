# static-weight-lock Specification

## Purpose
Defines when the static weights are locked under SSD streaming, so that a
prefill does not wait for the kernel to wire pageable weights when free memory
is at its floor.

## Requirements

### Requirement: Static weights locked when the wire limit allows
Under SSD streaming, the engine SHALL lock the static weights at engine open
when the planned wired total plus a margin for the GPU's transient wiring
stays under `vm.global_user_wire_limit`. This applies even when the 7/8
working-set budget would refuse. `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK=1`
SHALL leave them pageable.

#### Scenario: Full file cache
- **WHEN** the static weights were read and then 60 GiB of other file data, and a fresh bench process with `82GB` and a 32K context prefills the 2048-token prompt
- **THEN** the loader reports the static weights locked, and the prefill is within 2% of the warm-state prefill

#### Scenario: 256K context
- **WHEN** a bench session with the copy, `--boost` and `--ctx-alloc 262144` prefills 245760 tokens and decodes 256, at `80GB` and at `82GB`
- **THEN** the static weights are locked, every cache slot is locked ahead, and peak wired memory stays under the user wire limit

#### Scenario: No loss elsewhere
- **WHEN** the harness runs `decode`, `append` and `cold-2500,cold-7500`, A/B against the build without this change
- **THEN** no metric loses beyond its noise

### Requirement: Output unchanged
Locking SHALL NOT change any logits.

#### Scenario: Bitwise with and without the lock
- **WHEN** the bench dumps frontier logits at 2048 and 8192 with and without `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK`
- **THEN** every dump is byte-identical
