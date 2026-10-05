# dual-ssd-prefill Specification

## Purpose
Allows users with a second local SSD to supply an existing, content-validated replica for prefill weight reads without changing model output or the canonical model file.

## Requirements

### Requirement: Explicit opt-in and unchanged default
The engine SHALL accept `DS4_METAL_PREFILL_REPLICA` as an optional existing-GGUF path for single-box, non-quality, Q2 Metal SSD streaming. An absent or empty value SHALL preserve existing operation. Unsupported explicit requests SHALL fail before inference with a reason. The option SHALL NOT redirect ordinary decode expert reads.

#### Scenario: Default invocation
- **WHEN** the option is absent
- **THEN** the engine uses only its existing model sources and performs no replica access

#### Scenario: Unsupported explicit mode
- **WHEN** a nonempty replica is requested with TP, CPU, quality mode, nonstreaming mode or an unsupported routed-weight format
- **THEN** initialization fails naming the unsupported condition before producing tokens

#### Scenario: Decode after accelerated prefill
- **WHEN** a supported prefill completes with the option enabled
- **THEN** ordinary decode expert misses retain the canonical source

### Requirement: Validate externally consumed content
The engine SHALL open the supplied file read-only, require a regular compatible GGUF with valid range bounds, and establish byte identity of all routed-up ranges consumed from it against the canonical model before inference. Matching names, sizes or metadata alone SHALL NOT suffice. Validation SHALL use bounded memory independent of model size, occur once per engine rather than once per session, and retain the admitted file identity. A redundant same-inode source SHALL be rejected.

#### Scenario: Same layout with corrupt payload
- **WHEN** a replica has matching metadata but a changed routed-up byte
- **THEN** initialization rejects it before the differing bytes can reach inference

#### Scenario: Replaced source path
- **WHEN** a pathname is replaced after admission
- **THEN** the engine does not silently switch to the new file's contents

#### Scenario: Multiple sessions
- **WHEN** multiple sessions are created on an already admitted engine
- **THEN** they reuse the validated source identity without rescanning all replica weight bytes per session

### Requirement: Exact concurrent delivery within the existing budget
For supported explicit-buffer sweeps, the engine SHALL read absent routed-up bytes from the replica and absent gate/down bytes from the canonical model, permitting the two disk sources to make concurrent progress. It SHALL retain any accepted resident-cache reuse and the same expert-slot and layer-buffer budgets. It SHALL preserve token outputs, logits, state and numerical prefill partitions bit-for-bit. Sweeps not supported by the explicit-buffer path SHALL use the canonical path and identify that fallback.

#### Scenario: Two available disk sources
- **WHEN** a supported sweep needs uncached bytes from both sources
- **THEN** the sources can read concurrently and the engine waits for all required bytes before consuming the layer

#### Scenario: Same input and cache allocation
- **WHEN** an enabled run is compared with canonical-only execution on the same model and input
- **THEN** output logits and session state match bit-for-bit and admitted expert slots are unchanged

#### Scenario: Unsupported sweep shape
- **WHEN** a sweep cannot use the validated explicit-buffer path
- **THEN** it uses the existing canonical path without changing the numerical schedule and reports the fallback

### Requirement: Safe failure and no automatic storage changes
A failed read or cancellation SHALL NOT publish a partially filled layer or valid partial session. Outstanding work SHALL be settled before destination storage is freed or reused. Errors SHALL identify the source and propagate to the caller. The engine SHALL NOT create replicas, modify canonical weights or change disk configuration.

#### Scenario: Replica read fails after partial progress
- **WHEN** an external read returns an error or early EOF
- **THEN** the sweep fails, its partial session is invalid, and storage is not reused while another reader can still write it

#### Scenario: Missing replica
- **WHEN** the configured path does not exist
- **THEN** initialization fails without downloading or copying a replacement

### Requirement: Observable storage and validation costs
The engine SHALL report whether the option is active, the identities of admitted sources, validation bytes/time and bytes requested from each source. It SHALL distinguish initialization verification from inference IO, and SHALL NOT present aggregate disk bandwidth as a measured token-throughput gain.

#### Scenario: Performance evidence
- **WHEN** a benchmark uses the secondary source
- **THEN** its logs identify the placement and verification cost separately from the measured prefill work
