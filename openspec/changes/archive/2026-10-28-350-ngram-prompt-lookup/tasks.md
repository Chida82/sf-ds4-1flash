# Tasks

Runs after `320` by default. If `310` chose the lookup-first path, renumber this change below `320` and add `320`'s verifier tasks (its groups 1-3) here first, with this source.

## 1. Harness tool step

- [ ] 1.1 Add the `agent-replay` text (a source file, then a request to rewrite part of it; SHA-256 in `speed-bench/README.md`) and the kind to `ab_bench.py`, outside `all`, the mix and the record row. Verify an A/A on main: bitwise, no metric below zero.

## 2. Lookup source

- [ ] 2.1 `--ngram-spec N` in the CLI and the bench: the lookup over the session's token history (D2), the range check, and counters per source. Verify both spec scenarios of the lookup by running them.
- [ ] 2.2 The combination rule (D1) when `--dspark` is also given: length when `330` kept the threshold rule, expected rate when it kept the expected-cost rule; and whether the lookup keeps proposing during DSpark's back-off skips (measured both ways on `agent-replay` and `decode`). Verify the "Both sources" scenario.
- [ ] 2.3 Measure: B `--ngram-spec 5` and B `--dspark --ngram-spec 5` against `--dspark` alone, on `agent-replay`, `decode-code` and `decode`. Verify the keep rule on `agent-replay`, nothing below the rule on prose, and the token gate; append the rows to `perf-record.md`.

## 3. Server and docs

- [ ] 3.1 The flag in the server, if `340` has landed. Verify a one-client greedy request matches a server without it.
- [ ] 3.2 `README.md` (which workloads gain), `docs/upstream-prs.md` (#1167 `idea -> 350`). Verify there are no doc lines for V4 Flash-only behavior.

## 4. Integration

- [ ] 4.1 `make test`, parity without the flags, `openspec validate 350-ngram-prompt-lookup --strict`. No commit or push without a request.
