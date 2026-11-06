# long-context-index Specification

## Purpose
Defines how the V4.1 decode indexer selects and scores key blocks once the
compressed context is long, so that this child's output matches upstream's at
those lengths and every faster path can be switched off.

## Requirements

### Requirement: Long-context output matches upstream
For contexts from 32K to at least 72K tokens, greedy decode SHALL produce the
same logits, bit for bit, as upstream at this child's merge-base, on the same
GGUF, prompt and SSD streaming configuration.

#### Scenario: Frontier above 64K tokens
- **WHEN** the bench prefills the benchmark prose to 40000 and then to 72000 tokens in this child and in upstream `b3f5018`, dumping the logits after each frontier and after its last decoded token
- **THEN** every dumped logits file is byte-identical between the two

#### Scenario: Short contexts unchanged
- **WHEN** the same comparison runs at frontiers below 32K tokens
- **THEN** the logits are the ones this child produced before the change

### Requirement: Radix top-k candidate selection
From 16384 index rows, the decode indexer SHALL select its top-k key blocks
with a radix select that returns the same scores as the sort it replaces, for
every row count, including a row count that changes between calls; exactly
tied scores are ordered by id, as upstream's select orders them.
`DS4_METAL_DISABLE_V41_TOPK_SELECT=1` SHALL restore the sort.

#### Scenario: Kernel equality
- **WHEN** the kernel test selects top-k from random and tied scores at 16K to 256K keys in one process
- **THEN** the radix select and the sort return the same selection, with ties ordered by id

#### Scenario: Output follows upstream
- **WHEN** the bench decodes after 72000 tokens with the select on
- **THEN** the logits equal upstream `b3f5018`'s

### Requirement: Decode top-512 selection
A single-token decode that selects 512 key blocks SHALL use the top-512
selection (a block sort and prefix merges keeping only the first 512), and
SHALL return the same indices in the same order as the full selection.
`DS4_METAL_DISABLE_V41_DECODE_TOPK=1` SHALL restore the full selection with
bitwise identical output.

#### Scenario: Kernel equality
- **WHEN** the kernel test selects the top 512 from random and tied scores with both paths
- **THEN** the index lists are identical

#### Scenario: Switch is exact
- **WHEN** `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_DECODE_TOPK` runs
- **THEN** logits, Engram history and KV state are identical for every decoded token

### Requirement: Candidate-block scoring on later index layers
Above 2048 compressed blocks of 8 keys, index layers after layer 20 SHALL score
only the blocks that can still be selected, and the selection SHALL equal the
one obtained by scoring every block.

#### Scenario: Pruned scoring selects the same blocks
- **WHEN** the kernel test scores a layer past 20 with more than 2048 blocks both pruned and in full
- **THEN** the selected block lists are identical

### Requirement: Exact wide index scorer
From 8192 index rows, the FP4 index keys SHALL be scored one thread per key
with contraction disabled, giving the same scores, bit for bit, as the
row-per-threadgroup scorer. Non-FP4 keys SHALL not use it.

#### Scenario: Wide scorer bits
- **WHEN** the kernel test scores 8192 or more FP4 rows with the wide scorer and with the reference scorer
- **THEN** every score is bit-identical

#### Scenario: FP4-only gate
- **WHEN** the index keys are not FP4
- **THEN** the reference scorer runs
