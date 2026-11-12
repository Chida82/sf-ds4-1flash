# Spec Delta

## ADDED Requirements

### Requirement: A decision may think for a bounded number of tokens
With `"sf":{"think_tokens":N}`, 1 ≤ N ≤ 1024, each question SHALL be answered
after up to N greedy reasoning tokens, with `</think>` forced when the model
has not closed its reasoning, followed by the same readout as without
thinking. `usage.output_tokens` SHALL be the reasoning tokens generated.

#### Scenario: Budget reached
- **WHEN** a question runs with `think_tokens` 64 and the model does not close within 64 tokens
- **THEN** the `sf` object reports `think_tokens` 64 and `think_closed` `forced`, and the answer has probabilities summing to 1

#### Scenario: Deterministic
- **WHEN** the same request with `think_tokens` 64 runs twice
- **THEN** the option logits and the reasoning token counts are equal

#### Scenario: Zero is System One
- **WHEN** `think_tokens` is 0 or absent
- **THEN** the answers are bitwise those of the build before this change

### Requirement: The option is kept only if it buys accuracy
The option SHALL be kept only when the bench shows, for some N ≤ 256, an
accuracy 95% interval wholly above the accuracy at N = 0.

#### Scenario: Recorded curve
- **WHEN** the sweep finishes
- **THEN** `sysone-bench/record.md` holds one row per N and the decision
