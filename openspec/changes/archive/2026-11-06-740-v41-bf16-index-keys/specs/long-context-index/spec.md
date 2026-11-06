# Spec Delta

## ADDED Requirements

### Requirement: Long index rows scored from bf16 keys
From 8192 index keys, decode SHALL score each index row from a bf16 copy of the
FP4 index keys, written by the same kernels that write the f32 keys, and the
scores SHALL be bit-identical to scoring the f32 keys.
`DS4_METAL_DISABLE_V41_INDEX_BF16=1` SHALL skip the copy and score the f32 keys.

#### Scenario: Kernel equality
- **WHEN** the kernel test scores FP4 keys with block scales over 41 exponents from the bf16 copy and from the f32 cache
- **THEN** every score is bit-identical

#### Scenario: Restored keys that are not bf16-exact
- **WHEN** a restored session holds an index key that bf16 cannot represent
- **THEN** decode scores the f32 keys and prints one notice
