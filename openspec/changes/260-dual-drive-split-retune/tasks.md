# Tasks

## 1. Gate

- [ ] 1.1 Read `250` task 1.1's table. If no k has the copy's piece median below the internal drive's for the remaining pieces, record that S1 closes and skip to 3. Otherwise pick the two best k values. Verify the decision is written in `speed-bench/perf-record.md`.

## 2. Decode split (S1)

- [ ] 2.1 Hand the copy's fd to the Metal side when admitted (D2); pool tasks carry their descriptor; the fixed piece pattern behind `DS4_METAL_V41_DECODE_REPLICA_SPLIT=<k>` read per load; last-landing counters in the streaming summary (D3); a failed piece re-read from the model. Verify `make test`, `test-metal-ssd-experts`, `make test-deepseek41-prefill-replica REPLICA=<path>`, and the decode-switch test bitwise with the split on.
- [ ] 2.2 Harness `decode,append` with `guard-16896,guard-decode`, `--bitwise`, the copy admitted on both sides, B at each chosen k. Verify the keep rule; record the rows with the last-landing counts. Remove the code if no k is kept.

## 3. Prefill share (S2)

- [ ] 3.1 `DS4_METAL_PREFILL_REPLICA_READERS=<n>` (D4). Verify `make test-deepseek41-prefill-replica REPLICA=<path>` at n = 3 and 5.
- [ ] 3.2 Harness `cold,append`, `--bitwise`, n = 4 and 5 against 3. Verify a CI above zero on ttft before changing the default; record the rows.

## 4. Integration

- [ ] 4.1 Review against `AGENT.md`; switches and the replica paragraph in `AGENTS.md`; the README's second-drive section; `docs/upstream-prs.md` line for `DS4_ARGODRIVE_DECODE_WEIGHTS`; `make`, `make cpu`, `make test`, the model-backed checks and the parity oracle; `openspec validate 260-dual-drive-split-retune --strict`. No commit or push without a request.
