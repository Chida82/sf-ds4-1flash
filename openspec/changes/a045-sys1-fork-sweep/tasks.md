# Tasks

Expert. Ask the owner before starting. Requires `800`, `820`.

- [ ] 0.1 Step 0 profile at +300 and +1900 rows; record; stop if the read wait is gone at 1900.
- [ ] 1.1 `ds41_graph_fork_sweep` for branches only (no state tile), with the window, pending-pair and owner-tail save/restore; the batched head at layer 39.
- [ ] 1.2 Oracle 1 with branches of 20, 45 and 60 rows; oracle 2.
- [ ] 1.3 Add the state tile (forced carry, seed after the state); oracles again with a 1500-token state.
- [ ] 2.1 `ds4_session_fork_eval` and its refusals; a model-backed test target; `make test`, `make cpu` (the entry point must exist in the CPU build as a refusal).
- [ ] 2.2 Oracle 3: no diff in the existing sweep; parity oracle; `ab_bench.py --bitwise` on chat kinds.
- [ ] 3.1 `sf_sysone` path selection at 200 rows; calibration binding `readout`.
- [ ] 3.2 Bench: 10 and 30 questions on fresh and cached states against `800` and `a015`; accuracy against the `820` noise floor; record; apply the keep rule.
- [ ] 3.3 Docs: `docs/system-one.md`, `docs/SERVER.md`, `AGENTS.md` (the new function and why it is a sibling).
