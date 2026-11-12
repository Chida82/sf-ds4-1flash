# Tasks

Requires `810`; measurements need `820`.

## 1. Core split

- [x] 1.1 `sf_sysone_answer_from`; `sf_sysone_decide` rewritten on top of it. `make test` and `make test-sysone` pass unchanged (isolation and determinism still bitwise).

## 2. Cache

- [x] 2.1 `sysone_state_entry`, lookup (exact, longest extension, miss), store, eviction; flags `--sysone-state-cache`, `--sysone-state-cache-mb`; `ds4_help.c`.
- [x] 2.2 Unit tests of the design under `DS4_SERVER_TEST`.
- [x] 2.3 `sysone_job` uses the cache; the `sf` response object gains `"state_cache":"hit"|"extend"|"miss"`.

## 3. Chat preservation

- [x] 3.1 Save/restore around the decision with the `keep` rule; the failure path.
- [x] 3.2 Live test: chat, decision, chat continuation prefills only new tokens (assert on the `prompt`/prefill counts the server logs or returns in `usage`).

## 4. Measure

- [x] 4.1 `run.py --scenario repeat`; run it; record request-1, repeat and extension latencies and the changed-top share.
- [x] 4.2 Snapshot bytes and save/load ms at 2K, 8K, 32K. If load at 8K exceeds 150 ms, write the fallback note and stop there.

## 5. Docs

- [x] 5.1 `docs/SERVER.md`: the flags, the three lookup outcomes, the append-only note for growing states, the determinism note.
- [x] 5.2 `docs/system-one.md`, "Measured": the repeat table.
