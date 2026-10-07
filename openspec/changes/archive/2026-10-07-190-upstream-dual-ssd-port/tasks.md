# Tasks

## 1. Port (approach A)

- [x] 1.1 In `~/github/chida82/ds4`, branch `dual-ssd-prefill-v41` from `main` (`0aaea5a`). Read ds4's Metal model-map registration and prefill page-in for V4.1, and confirm D1's binding point. If a second mapping would touch shared code beyond V4.1's prefill, stop and report. Verify: the binding point and the planned diff size are written in this change's design.
- [x] 1.2 Implement D1/D2 for V4.1 Flash. Verify: ds4's own build and tests pass, an invalid or changed copy is refused, and greedy output with the copy is token-identical to output without it on the parity prompts.

## 2. Measurement

- [x] 2.1 Run D3: original ds4 against the port, alternated, same GGUF and copy. Verify: a perf-record section with per-shape gains and spreads, and a `docs/upstream-prs.md` line.

## 3. Owner decision

- [x] 3.1 Report the A numbers to the owner with the D4 options (explicit buffers plus `140`, others), then do only what they choose. Verify: the decision is recorded; nothing is pushed or proposed upstream without an explicit request; `openspec validate 190-upstream-dual-ssd-port --strict` passes.

## Outcome (2026-10-07)

- 1.2: fork branch `dual-ssd-prefill-v41`, local commit `683e062`. Builds without warnings; model-less tests and `test-deepseek41-metal` pass; missing, self and wrong-size copies are refused; frontier logits are bitwise identical with and without the copy and against `0aaea5a`. `ds4_test` needs the V4 Flash GGUF, absent here, on `main` as on the branch. The content-differs and changed-after-check paths are `140`'s code unchanged and were not exercised (they need a second 341 GiB copy).
- 2.1: prefill -13% to -38% against original ds4, decode unchanged (perf-record, Dual-drive port to upstream ds4; `docs/upstream-prs.md`, Outgoing ports).
- 3.1: decided overnight under the owner's "decidi te": no nice-to-have was started. Approach A is a net loss. The D4 port of the explicit buffers (`60`/`100`, then `140`) is the path that carries the gain, and it is a much larger diff. It stays the owner's call. Nothing was pushed or proposed upstream.
