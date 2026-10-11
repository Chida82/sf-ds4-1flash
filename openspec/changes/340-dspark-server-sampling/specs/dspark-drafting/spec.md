# Spec Delta

## MODIFIED Requirements

### Requirement: No drafting at non-zero temperature
When sampling with a temperature above zero, drafting SHALL use exact speculative sampling. Each generated token's distribution SHALL equal the distribution of ordinary sampling with the same settings. Drafts that would change that distribution SHALL NOT be accepted.

#### Scenario: Sampled request
- **WHEN** the CLI runs with `--dspark` and a temperature of 0.6
- **THEN** it drafts, and the counters show accepted drafted tokens

#### Scenario: Distribution kept
- **WHEN** the same prefix is sampled many times with and without `--dspark` at the same settings
- **THEN** the two empirical distributions of the next token do not differ by a chi-square test at the 1% level

## ADDED Requirements

### Requirement: Server drafting for a single request
`sf-ds4-1flash-server` SHALL accept `--dspark`, `--mtp-model` and `--dspark-confidence` with the same rules as the CLI. A request SHALL draft only while it is the only active decode. While other decodes are pending, the server SHALL decode plainly.

#### Scenario: One client
- **WHEN** one client sends a chat request to a server started with `--dspark`
- **THEN** the response is generated with drafting, and a greedy request returns the same text as a server without the flag

#### Scenario: Two clients
- **WHEN** a second request arrives while the first is decoding
- **THEN** both decode without drafting until one of them is the only active decode again

### Requirement: Sampling-mode boundaries cut the accepted block
When a block of accepted tokens contains a token after which the sampling mode changes (into or out of tool-call syntax, or out of thinking), the engine SHALL keep the tokens up to and including that token. It SHALL discard the rest as if rejected, and SHALL choose the next token under the new mode. The context SHALL NOT be rebuilt.

#### Scenario: Entering a tool call
- **WHEN** a sampled response with `--dspark` starts tool-call syntax inside an accepted block
- **THEN** the tool-call tokens are chosen greedily, as without the flag, and the server log shows no context rebuild

### Requirement: Cache reuse with drafting
Live KV reuse and disk KV checkpoints SHALL work with drafting on. A checkpoint SHALL never contain rows that were rejected.

#### Scenario: Second turn
- **WHEN** a two-turn conversation runs against a server with `--dspark`
- **THEN** the second turn reuses the first turn's cached prefix, and a greedy second turn matches a server without the flag
