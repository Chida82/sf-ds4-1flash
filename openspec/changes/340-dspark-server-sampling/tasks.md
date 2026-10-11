# Tasks

Starts after `320` has landed (`330` may run before or after).

## 1. Exact sampling

- [ ] 1.1 Enable #1073's exact branch for a temperature above zero, and remove `320`'s notice. Verify the "Sampled request" scenario and `make test-dspark-distribution` (D4).

## 2. Server

- [ ] 2.1 Add `--dspark`, `--mtp-model` and `--dspark-confidence` to the server, and draft only while one decode is active (D3). Verify both server scenarios: one client greedy matches a server without the flag; two clients decode plainly.
- [ ] 2.2 The boundary cut (D2): the cycle takes the caller's mode check and rolls back after the cut. Verify the tool-call scenario and a test with a forced boundary at each draft position.
- [ ] 2.3 KV reuse and disk checkpoints with drafting. Verify the two-turn scenario, and that no checkpoint written during a test contains a rolled-back position.

## 3. Measurement and docs

- [ ] 3.1 The single-client bench (D4), plain against `--dspark`, on code, chat, tool and prose request sets. Record medians and CIs in `perf-record.md`. Verify that the greedy sets are token-identical.
- [ ] 3.2 `README.md` (which request kinds gain under the server), `docs/SERVER.md` (the flags and the single-request rule), and `docs/upstream-prs.md` (`fc80bd6`: `idea -> 340`). Verify there is no doc line claiming opportunistic sampling.

## 4. Integration

- [ ] 4.1 `make test`, parity without the flag, `openspec validate 340-dspark-server-sampling --strict`. No commit or push without a request.
