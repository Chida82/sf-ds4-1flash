# Spec Delta

## MODIFIED Requirements

### Requirement: Scenario kinds
The harness SHALL measure the decode, prompt and append kinds below, each
selectable by name, and the groups `cold` (the five cold kinds), `guards` (the
two guard kinds) and `all` (every kind but the guards and `decode-code`). The
prompt is the child's benchmark prose text, except for `decode-code`, whose
prompt is the child's benchmark code text. The harness SHALL refuse an
invocation that selects no kind.

#### Scenario: Prefill change
- **WHEN** the harness runs with `--kinds cold,append`
- **THEN** the five cold kinds and `append` are measured and no decode kind starts

#### Scenario: No kind
- **WHEN** neither `--kinds` nor `--guards` is given
- **THEN** the harness exits 2 listing the kinds and groups

#### Scenario: Code decode is never implicit
- **WHEN** the harness runs with `--kinds all`
- **THEN** `decode-code` does not run

### Requirement: Decode kinds
The decode kinds SHALL be:

| Kind | Context frontiers | Generated tokens per frontier | Metrics |
|---|---|---|---|
| `decode` | 2048, then 8192 on top of it | 256 | steady decode tokens/s at 2048 and at 8192; first-token ms as detail |
| `decode-code` | 2048, then 8192 on top of it, on the code text | 256 | steady decode tokens/s at 2048 and at 8192; first-token ms as detail |
| `guard-decode` | 8192 | 2500 | steady decode tokens/s over 2500 tokens |

`decode-code` SHALL NOT enter the typical-mix estimate or the record row. Its metrics SHALL appear in the summary.

#### Scenario: Decode kind
- **WHEN** the `decode` kind runs
- **THEN** it generates 256 tokens after a 2048 context and 256 after extending it to 8192, and reports steady decode at both

#### Scenario: Code decode kind
- **WHEN** the `decode-code` kind runs with B's benchmark given `--dspark --mtp-model FILE`
- **THEN** both builds decode the code text at 2048 and 8192, the token gate compares them, and the summary reports both gains with their intervals
