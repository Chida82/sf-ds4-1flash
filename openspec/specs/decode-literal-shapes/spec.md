# decode-literal-shapes Specification

## Purpose
Defines the V4.1 decode kernels specialized to the model's fixed shapes:
where they run, that they compute the same bits as the generic kernels, and
the switches that restore those kernels.

## Requirements

### Requirement: Literal q_a/kv projection
A single-row decode of the paired q_a/kv projection (5120 inputs, 1280 and 512
outputs, two rows per simdgroup) SHALL run a kernel with those dimensions
compiled in, and SHALL produce the same bits as the generic paired kernel.
`DS4_METAL_DISABLE_V41_LITERAL_SHAPES=1` SHALL restore the generic kernel.

#### Scenario: Kernel equality
- **WHEN** the kernel test runs the paired projection on random Q8_0 weights with the literal and the generic kernel
- **THEN** both outputs are bit-identical

### Requirement: Literal output-B expand
A single-row decode of the 8192 -> 5120 output-B expand without an add SHALL
run a kernel with those dimensions compiled in, producing the same bits as the
generic expand kernel, under the same switch.

#### Scenario: Kernel equality
- **WHEN** the kernel test runs the expand with the literal and the generic kernel
- **THEN** the four HC streams are bit-identical

#### Scenario: Other shapes keep the generic kernel
- **WHEN** the expand runs with an add, more than one row, or other dimensions
- **THEN** the generic kernel runs

### Requirement: Engram gate reduction over a threadgroup
The unmasked Engram gate of width 5120 and at most 16
rows SHALL reduce over 256 threads and produce the same bits as the
single-simdgroup kernel. `DS4_METAL_DISABLE_V41_SPLIT_REDUCE=1` SHALL restore
that kernel.

#### Scenario: Kernel equality on this machine
- **WHEN** the kernel test runs the gate with both kernels on the M5 Max
- **THEN** every output is bit-identical

### Requirement: Switches are exact end to end
Each switch this change adds SHALL leave decoded logits, Engram history and KV
state bitwise identical.

#### Scenario: Decode switch test
- **WHEN** `make test-deepseek41-decode-switch SWITCH=<switch>` runs for each switch
- **THEN** every decoded token matches
