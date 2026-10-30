# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request. Starts from `620` landed.

## 1. Session flag and scales

- [x] 1.1 Add `steering_on` to `ds4_session`, `ds41_engine_steered`, and `ds41_steering_arm`, set at `ds4_session_create` (design D1, D2). Verify `make` builds with no warning and `make test` passes.
- [x] 1.2 Route `ds41_steering_apply_gates`, `ds41_steering_on_prompt` and `ds41_steering_on_decode` through the flag (D2). Verify by `git grep -n "residual_scale\b\|residual_scale2\b\|closure_scale\b" ds4.c`: every write to the graph's scales goes through `apply_gates` or `arm`. Record the list in this change's design.

## 2. Setter

- [x] 2.1 Add `ds4_session_set_steering` and `ds4_session_steering` to `ds4.c`/`ds4.h` with the order of D3 (same value, no profile, distributed, invalidate, set, arm). Verify with model-less tests in `make test`: an error without a profile, a no-op on the same value (the test checkpoint keeps its tokens), and an error on a session marked distributed.

## 3. Batch and persistence

- [x] 3.1 Replace the engine-wide decline in `ds4_sessions_batch_supported` with the per-item rule of D4. Verify with a model-less test of the four cases (all off; all on with a constant profile; all on with a gated profile; mixed).
- [x] 3.2 `ds41_steering_refuses_persistence` reads `steering_on` (D5). Verify with a model-less check that a session with steering on is refused even with both graph scales at zero, and a session with steering off is not.

## 4. Model-backed proof

- [x] 4.1 Add `--steering-session PROFILE PROMPT_FILE` to `tests/test_deepseek41_graph.c` and `make test-deepseek41-steering-session` (D6: cases 1 and 2, 32 GiB cache, engines in sequence). Verify both cases print equal digests on `sf-ds4-1flash-candor` with `speed-bench/promessi_sposi.txt`, and that case 2 reports a full re-prefill.
- [x] 4.2 CLI on-path check: the candor profile on one fixed prompt, greedy, thinking on and off, on main (after `620`) and on the branch. Verify the texts are byte-identical.

## 5. Docs and verification

- [x] 5.1 `AGENTS.md` Identity "Steering" row: the profile is per session, on by default in CLI/eval, and switching drops live state. Verify the row states all three.
- [ ] 5.2 `make test` (read the names of the tests that ran), `make cpu`, and `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from the StarForge checkout. Verify all pass.
- [x] 5.3 `openspec validate 630-session-steering-switch --strict`. Verify it passes.

Notes from the implementation:
- 1.2: the graph's scales are written only by `ds41_steering_apply_gates` (gated/scheduled path), `ds41_steering_arm` (the setter) and `ds4_session_create` (the uploads, equal to arming "on"); `e->closure_scale` is the engine's, set by the profile loader.
- 2.1: model-less, through `tests/test_session_state_gpu --steering-switch`, now run by `make test-session-state` (the GPU build of that file was built but never run; its other cases fail there today, so only this case runs). The distributed/TP refusal is checked with `tp.active` on a fake engine.
- 3.1: the rule is `ds41_steering_batch_ok`, tested on fake sessions for all off, all on constant, all on gated, all on scheduled, mixed, and all off under a scheduled profile.
- 4.1: PASS on the 1017 GGUF, prefix 2047 of `promessi_sposi.txt`, 65 states each: no profile == profile with the session off; a steered session differs at the first state, and switched off it reports position 0 and then matches the no-profile run.
- 4.2: CLI candor run (same prompt and flags as `620` 1.1), thinking on and off: byte-identical to the `620` baseline.
- 5.2: `make test` and `make cpu` pass; the parity oracle runs from the StarForge checkout against the child's main checkout and is left open.
