# Spec Delta

## MODIFIED Requirements

### Requirement: Explicit opt-in and unchanged default
The engine SHALL accept `DS4_METAL_PREFILL_REPLICA` as an optional existing-GGUF path for single-box, non-quality, Q2 Metal SSD streaming. An absent or empty value SHALL preserve existing operation. Unsupported explicit requests SHALL fail before inference with a reason. Ordinary decode expert reads SHALL use the replica only as the `dual-ssd-decode-misses` capability allows.

#### Scenario: Default invocation
- **WHEN** the option is absent
- **THEN** the engine uses only its existing model sources and performs no replica access

#### Scenario: Unsupported explicit mode
- **WHEN** a nonempty replica is requested with TP, CPU, quality mode, nonstreaming mode or an unsupported routed-weight format
- **THEN** initialization fails naming the unsupported condition before producing tokens

#### Scenario: Decode after accelerated prefill
- **WHEN** a supported prefill completes with the option enabled
- **THEN** ordinary decode expert misses read the replica only for validated ranges, and every other byte from the canonical source
