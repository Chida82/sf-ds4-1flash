# Spec Delta

## ADDED Requirements

### Requirement: Prompt-lookup draft source
`--ngram-spec N` SHALL enable a draft source that proposes up to N tokens, with N from 1 to the verifier's cap. They are the tokens that followed the most recent earlier occurrence, in the session's context, of the last three tokens. No weights are loaded. Greedy output SHALL stay identical to output without the flag. An N outside the range SHALL be refused at startup.

#### Scenario: Copy from context
- **WHEN** a greedy request asks to rewrite a function that is in the prompt, with `--ngram-spec 5`
- **THEN** the counters show accepted lookup drafts and the output equals the output without the flag

#### Scenario: Out of range
- **WHEN** `--ngram-spec 0` is given
- **THEN** the engine exits naming the valid range

### Requirement: Combined sources
When both `--dspark` and `--ngram-spec` are given, each cycle SHALL verify the longer of the two proposals: the lookup draft and DSpark's confident prefix. The counters SHALL report accepted tokens per source.

#### Scenario: Both sources
- **WHEN** a greedy agent-replay request runs with `--dspark --ngram-spec 5`
- **THEN** the counters show accepted tokens from each source and the output equals the output with neither flag
