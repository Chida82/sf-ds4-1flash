# Tasks

This revision narrows the former task 1.1 to CLI/server. Checked items record existing work, not tests run while revising these artifacts. Former composite task 4.1 is split below; parity is not implied by build success. No commit/push authority is conveyed by this checklist.

## 1. Admission implementation and contract

- [x] 1.1 Implement the CLI/server opt-in and engine option; existing `ds4_cli.c`, `ds4_server.c`, `ds4.h` and help entries establish this portion of the former partial task. Bench is intentionally excluded.
- [x] 1.2 Gate only the steering-file term and preserve the upstream error; the existing predicate and previously recorded byte comparison establish this implementation.
- [x] 1.3 Classify the environment variable in `ds4_env.def`; the previous env-check and startup report verified it is recognized.
- [x] 1.4 (`tests/test_steering_admission.py`: the variable is removed from every run's environment, then unset, `""`, `0`, `1` and the flag are tried; `ds4_env.def` and `--help` state the presence semantics. Model-backed, 2026-10-13: PASS.) Add repeatable checks of unset/empty/`0`/`1` environment semantics and the independent CLI flag, clearing inherited opt-ins. Verify the truth table in design D2 and update the option documentation with the same semantics.
- [x] 1.5 Update `README.md` and `dir-steering/README.md` to describe admission only, CLI/server scope and the lack of live legacy FFN/attention hooks. Verify commands do not suggest that admission alone enables a V4.1 edit; link to `401`'s application contract.
- [x] 1.6 Add the child-divergence entry to `docs/upstream-prs.md`. Verify it attributes the gate to this change, not an upstream PR, without claiming efficacy.

## 2. Gate regressions and state identity

- [x] 2.1 Preserve the historical engine smoke result: without opt-in a file produced the exact upstream line and exit 1; with opt-in startup proceeded. This does not replace the reusable regression below.
- [x] 2.2 (Same script, second half of `make test-deepseek41-steering-admission`: default refusal and `--power 50` under the opt-in both print upstream's line verbatim with exit 1 and empty stdout; the four opt-ins admit `--dir-steering-residual 0` and print the unsteered completion. Model-backed, since the gate runs after the GGUF opens: PASS.) Add a runnable regression for default refusal and opt-in plus an independently unsupported condition. Use explicit residual scale zero when integrating with `401`; verify exact stderr and exit status, not just non-empty output. Label model-required cases accurately.
- [x] 2.3 (`./tests/test_deepseek41_graph deepseek-v4.1-flash.gguf --steering-admission speed-bench/promessi_sposi.txt`, DeepSeek-V4.1-Flash-Q2, 32 GiB cache, 2026-10-13: no opt-in, opt-in alone, opt-in with a zero-scale file; 65 logits per step and the final KV/Engram spans bitwise after 511- and 2047-token prefixes, `residual_dirs` NULL and no CPU directions, the file refused without the opt-in. Output: "V4.1 steering admission: ... PASS". The 64 GiB first draft froze the machine: a closed engine's cache stays wired in-process, see AGENTS.md.) Extend/reuse `tests/test_deepseek41_graph.c` and the decode-switch target for baseline versus opt-in/no-file and opt-in/file/all-zero-scales. Verify 65 steps of logits, KV and Engram bitwise and confirm no direction allocation; record model, command and test output.

## 3. Integration

- [x] 3.1 (2026-10-13, after the model-backed checks and parity: `make test` exit 0 with every named test in its output: env-check 503 names, session state, Engram, Q4_K and MXFP4 4/4, TP commands/bulk/cancel/logits, RDMA, Unix/TCP links, eval 92+50 cases, `ds4_test --server`, prompt prefix, sampling, vision image, image decode, slab residency, prefill dispatch, expert discard/stream. `openspec validate 400-steering-gate-optin --strict`: valid.) Run `make test` on the integrated revision, read the named tests in its output, and run `openspec validate 400-steering-gate-optin --strict`. Record results separately from historical build/env-check reports.
- [x] 3.2 (`SF_CHILD_DIR=<this worktree> SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash <model>`, 2026-10-13 17:06: the oracle logged `building child (sf-ds4-1flash @ a839eb1)` against upstream `fc80bd6`; `PARITY OK (10 prompts)`, ten `[ok ]`, child +19% to +185% per prompt, no speed trip; `tools/parity/out/sf-ds4-1flash-20261013-170638`. `SF_CHILD_DIR` is a one-line addition to StarForge `tools/lib.sh`, since the registry path is the `main` checkout.) Run the default-path parity oracle from StarForge with SSD streaming and without the opt-in. Verify it targets the candidate worktree/build, not a stale child binary; record token parity and the required speed guard. Do not mark complete while the run is pending.

## Workflow follow-up

- Continue with `401` for active-site correctness; 400 is not an efficacy gate.
- Commit, push and archive only on a separate explicit request.
