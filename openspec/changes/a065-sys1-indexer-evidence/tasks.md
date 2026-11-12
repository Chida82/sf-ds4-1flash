# Tasks

Requires `810` and `820`. Edits `ds4.c`: follow the design and stop at
anything it does not list.

## 1. Probe

- [ ] 1.1 Edits (a), (b), (c); the `ds4_env.def` line; the note on `g->pos` in the PR text. `make test` passes and names `env-check`; `make cpu` builds.
- [ ] 1.2 Guard with the variable unset: `make test-deepseek41-metal`, `make test-sysone`, `ab_bench.py --kinds decode --bitwise`.
- [ ] 1.3 Server: `state_token_start`, `token_bytes` under `sf.debug`; the unit test on their sum.

## 2. Stage 1

- [ ] 2.1 `sysone-bench/evidence_items.py` (30 hand-written Italian facts in the file, seed fixed) and `evidence_eval.py`; unit tests in `tests/test_sysone_bench.py`: token-to-line mapping on a synthetic `token_bytes`; recall@5 and MRR on hand-made scores; prior subtraction.
- [ ] 2.2 The run (about 30 minutes). Check the probe file holds one record per request with `n` equal to the request's total tokens.
- [ ] 2.3 Tables in `sysone-bench/record.md`; apply the gate.

## 3. Stage 2 (only by the gate)

- [ ] 3.1 The capture tensor as the design says; if the allocation cannot be conditional, stop and show the owner the diff.
- [ ] 3.2 The copy in `ds41_graph_step`, the eight-slot dump, the 1.2 guard again.
- [ ] 3.3 Per-layer tables; apply the gate.

## 4. Deliverable

- [ ] 4.1 `docs/system-one.md`, "Evidence": tables and the recommendation.
- [ ] 4.2 On "stop": revert the engine edits; `git diff main -- ds4.c ds4_env.def` prints nothing; `make test` passes.
- [ ] 4.3 On "follow up": the list in the docs; ask the owner before opening the next change.
