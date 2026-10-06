# Tasks

## 1. Port (approach A)

- [ ] 1.1 In `~/github/chida82/ds4`, branch `dual-ssd-prefill-v41` from `main` (`0aaea5a`). Read ds4's Metal model-map registration and prefill page-in for V4.1, and confirm D1's binding point. If a second mapping would touch shared code beyond V4.1's prefill, stop and report. Verify: the binding point and the planned diff size are written in this change's design.
- [ ] 1.2 Implement D1/D2 for V4.1 Flash. Verify: ds4's own build and tests pass, an invalid or changed copy is refused, and greedy output with the copy is token-identical to output without it on the parity prompts.

## 2. Measurement

- [ ] 2.1 Run D3: original ds4 against the port, alternated, same GGUF and copy. Verify: a perf-record section with per-shape gains and spreads, and a `docs/upstream-prs.md` line.

## 3. Owner decision

- [ ] 3.1 Report the A numbers to the owner with the D4 options (explicit buffers plus `140`, others), then do only what they choose. Verify: the decision is recorded; nothing is pushed or proposed upstream without an explicit request; `openspec validate 190-upstream-dual-ssd-port --strict` passes.
