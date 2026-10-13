# Tasks

This revision narrows the former task 1.1 to CLI/server. Checked items record existing work, not tests run while revising these artifacts. Former composite task 4.1 is split below; parity is not implied by build success. No commit/push authority is conveyed by this checklist.

## 1. Admission implementation and contract

- [x] 1.1 Implement the CLI/server opt-in and engine option; existing `ds4_cli.c`, `ds4_server.c`, `ds4.h` and help entries establish this portion of the former partial task. Bench is intentionally excluded.
- [x] 1.2 Gate only the steering-file term and preserve the upstream error; the existing predicate and previously recorded byte comparison establish this implementation.
- [x] 1.3 Classify the environment variable in `ds4_env.def`; the previous env-check and startup report verified it is recognized.
- [ ] 1.4 Add repeatable checks of unset/empty/`0`/`1` environment semantics and the independent CLI flag, clearing inherited opt-ins. Verify the truth table in design D2 and update the option documentation with the same semantics.
- [ ] 1.5 Update `README.md` and `dir-steering/README.md` to describe admission only, CLI/server scope and the lack of live legacy FFN/attention hooks. Verify commands do not suggest that admission alone enables a V4.1 edit; link to `401`'s application contract.
- [ ] 1.6 Add the child-divergence entry to `docs/upstream-prs.md`. Verify it attributes the gate to this change, not an upstream PR, without claiming efficacy.

## 2. Gate regressions and state identity

- [x] 2.1 Preserve the historical engine smoke result: without opt-in a file produced the exact upstream line and exit 1; with opt-in startup proceeded. This does not replace the reusable regression below.
- [ ] 2.2 Add a runnable regression for default refusal and opt-in plus an independently unsupported condition. Use explicit residual scale zero when integrating with `401`; verify exact stderr and exit status, not just non-empty output. Label model-required cases accurately.
- [ ] 2.3 Extend/reuse `tests/test_deepseek41_graph.c` and the decode-switch target for baseline versus opt-in/no-file and opt-in/file/all-zero-scales. Verify 65 steps of logits, KV and Engram bitwise and confirm no direction allocation; record model, command and test output.

## 3. Integration

- [ ] 3.1 Run `make test` on the integrated revision, read the named tests in its output, and run `openspec validate 400-steering-gate-optin --strict`. Record results separately from historical build/env-check reports.
- [ ] 3.2 Run the default-path parity oracle from StarForge with SSD streaming and without the opt-in. Verify it targets the candidate worktree/build, not a stale child binary; record token parity and the required speed guard. Do not mark complete while the run is pending.

## Workflow follow-up

- Continue with `401` for active-site correctness; 400 is not an efficacy gate.
- Commit, push and archive only on a separate explicit request.
