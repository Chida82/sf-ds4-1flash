# Spec Delta

## Purpose

Defines opt-in speculative decoding with DeepSeek V4.1 Flash's own DSpark drafter under SSD streaming. It covers how it is enabled, what it may and may not change in the output, how much it drafts, when it stops drafting, and what it reports.

## ADDED Requirements

### Requirement: Drafting is opt-in
Speculative decoding SHALL run only when `--dspark` is given. Without the flag, decode SHALL be bitwise identical to the build before drafting existed, and no drafter memory SHALL be allocated.

#### Scenario: Flag absent
- **WHEN** the CLI or the benchmark runs without `--dspark`
- **THEN** the generated tokens and logits are bitwise identical to the previous build's, and the startup output shows no drafter

### Requirement: Support file
`--dspark` SHALL require `--mtp-model FILE`, which names a V4.1 Flash DSpark support GGUF. The engine SHALL refuse to start, with a message naming the field, when the file is missing or unreadable, or when its metadata does not match the main model: stage count, block size, target layers or hidden size. At startup it SHALL print the drafter's resident size.

#### Scenario: Wrong support file
- **WHEN** `--dspark --mtp-model` names a support GGUF built for another model
- **THEN** the engine exits before loading the main model's experts, naming the mismatching field

#### Scenario: Flag without file
- **WHEN** `--dspark` is given without `--mtp-model`
- **THEN** the engine exits with a message that `--dspark` requires `--mtp-model FILE`

### Requirement: Runs under SSD streaming
Drafting SHALL work with `--ssd-streaming` and any admitted expert cache. The drafter's weights SHALL stay resident beside the expert cache.

#### Scenario: Streaming run
- **WHEN** the CLI runs with `--ssd-streaming --dspark --mtp-model FILE`
- **THEN** it generates text, and the expert-cache counters include the reads made for verified rows

### Requirement: Greedy output is unchanged
At temperature zero, the tokens generated with `--dspark` SHALL be identical to those generated without it, for the same model, prompt, context size and expert cache.

#### Scenario: Harness token gate
- **WHEN** the harness runs A without and B with `--dspark` on any kind
- **THEN** the token gate passes on every frontier

### Requirement: No drafting at non-zero temperature
When sampling with a temperature above zero, the engine SHALL decode without drafting and SHALL say so once per process.

#### Scenario: Sampled request
- **WHEN** the CLI runs with `--dspark` and a temperature of 0.6
- **THEN** one notice says drafting is off for sampled decoding, and decoding proceeds as without the flag

### Requirement: Draft length per cycle
Each cycle SHALL draft the longest prefix of the drafter's block whose confidence is at or above the threshold, capped by the default cap, the end-of-sequence token and the context end. `--dspark-confidence X` SHALL set the threshold. A value outside [0, 1] SHALL be refused at startup.

#### Scenario: Threshold override
- **WHEN** `--dspark-confidence 1.5` is given
- **THEN** the engine exits naming the valid range

### Requirement: Back-off when drafting does not pay
When drafting cycles yield fewer tokens per second than ordinary cycles, the engine SHALL decode without drafting for a growing number of cycles. Afterwards it SHALL draft again to measure anew.

#### Scenario: Prose that the drafter predicts poorly
- **WHEN** a long greedy decode of prose runs with `--dspark`
- **THEN** most cycles after the first few are ordinary decode steps, and the benchmark reports the skipped cycles

### Requirement: Drafting statistics
With `--dspark`, the benchmark SHALL print after each frontier these counts, accumulated so far:
- drafting cycles and ordinary cycles;
- drafted tokens;
- accepted tokens by draft position;
- cycles skipped by back-off.

#### Scenario: Per-frontier deltas
- **WHEN** the benchmark runs two frontiers with `--dspark`
- **THEN** a reader can take the difference of the two printed counter sets to get the second frontier's acceptance per position

### Requirement: Unsupported combinations are refused
The engine SHALL refuse to start with `--dspark` together with tensor-parallel or pipeline distribution, naming the mode.

#### Scenario: Tensor parallel
- **WHEN** the CLI is started with `--dspark` and a tensor-parallel peer
- **THEN** it exits naming tensor parallelism as unsupported with `--dspark`
