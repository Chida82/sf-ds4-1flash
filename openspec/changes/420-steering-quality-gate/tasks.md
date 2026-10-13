# Tasks

Runs on the tree where the last of `401` to `405` landed, one model process at a time, in the session's own shell, each result recorded with command, model, date and output. No commit, push or archive without a separate explicit request.

## 1. Bits

- [ ] 1.1 `make test`: exit 0 with every test named in the output, including the steering fold, file validation and converter self-check.
- [ ] 1.2 `make test-deepseek41-decode-switch SWITCH=<env>` for every switch `AGENTS.md` documents as bitwise, and `DS4_METAL_DISABLE_V41_RESIDUAL_STEERING` with no file: all exact.
- [ ] 1.3 `make test-deepseek41-steering-admission` (state controls and CLI/server gate) and `make test-deepseek41-steering-routes`: PASS.

## 2. Parity

- [ ] 2.1 Parity oracle from StarForge, `SF_CHILD_DIR=<tree> SF_PARITY_FLAGS=--ssd-streaming`, no steering options: ten token-identical prompts, no speed trip; record the output directory and the upstream SHA.

## 3. Results

- [ ] 3.1 A/B harness of the tree against the start commit of the current `perf-record.md` segment, steering off, `--bitwise`, every kind: logits bitwise, no throughput metric's pooled interval wholly below zero; append the printed row to the record, naming the steering series as the step.
- [ ] 3.2 Collect in one table, with dates, commands and intervention identity: the steered overhead of `401`, the KPIs `402` has produced, and any `403`/`404`/`405` numbers; mark results under an older revision as history.
- [ ] 3.3 Write the go/no-go list; a loss or a mismatch is named by kind and interval and opens its own change, nothing is fixed here.

## Workflow follow-up

- Commit, push and archive only on a separate explicit request.
- A steering change landing after this gate ran means the gate runs again.
