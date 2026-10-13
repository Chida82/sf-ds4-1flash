# Tasks

No temporal implementation is complete. Depends on corrected `401` and the applicable `402` protocol. Former mandatory smoothstep/think tasks are now conditional. A conditional item is checked only after implementation plus its stated check, or after recording an evidence-backed not-retained decision under design D4; an unrun experiment is not a negative result. The task groups below replace the old 0.1-temperature sweep and outdated source-alpha grid.

## 1. Constant baseline and bounded temporal experiment

- [ ] 1.1 Pin the corrected site/revision, vector, mask, decoding, development/holdout split and acceptance margins using `402`. Run the long-output benign pilot and identify the best constant comparator with a declared budget; verify raw evidence and full-response/fidelity metrics exist rather than relying on old first-token findings.
- [ ] 1.2 Implement task-local constant/prefill-only/decode-only/initial-window candidates using the existing graph/test machinery, without exposing permanent release flags. Add a small timing/state fixture; verify the declared first-token semantics and unchanged disabled behavior for each arm.
- [ ] 1.3 Run the bounded temporal comparison at greedy temp 0 with matched prompt policy and comparable tuning budgets. Retain complete-response, benign, over-refusal and capability evidence; verify no screen-only result is used for adoption and report any measured enabled cost separately.
- [ ] 1.4 If a time-limited intervention shows merit, compare a simple linear ramp with cubic smoothstep on the same development protocol and verify on holdout. Otherwise record the failed/unresolved temporal gate with evidence and do not build the release schedule.
- [ ] 1.5 Record the baseline, candidate definitions, uncertainty and retained/not-retained decision in this design's results section and the appropriate evidence reference; update `dir-steering/README.md` only to describe an actual result or available mechanism. Verify no inherited alpha range or curve is called the V4.1 winner without measurement.

## 2. Retain only the winning schedule (conditional on group 1)

- [ ] 2.1 If adopted, promote the simplest winning shape with the minimal controls of design D3 and test it: endpoints, `N=0` constant fallback bitwise, finite/range validation, the predicted-position rule on the final prompt forward, per-session state with interleaved sessions, and rejection of unsupported batching and persistent prefix reuse under the `401` guard. Update help, env classification if needed and schedule documentation with it. If not adopted, record the not-retained decision with the group-1 evidence and add no flags.

## 3. Phase schedule and phase vector (separate conditional gates)

- [ ] 3.1 Measure thinking/final-answer outcomes under the retained schedule or constant baseline with `402`. Only on a measured phase-specific gap implement and test the same-vector phase schedule (initialized from the effective template and actual boundary token IDs; a long thinking block restarts the answer dose; missing/truncated boundaries handled explicitly) and compare it on holdout; only on a remaining measured gap consider a separately derived second vector under `401` validation. Record negative gates instead of shipping unused options, and document only retained phase controls with their evidence.

## 4. Integration

- [ ] 4.1 Run `make test` with named test output and disabled-path parity for any runtime change, then `openspec validate 403-steering-decay-phase-runtime --strict`. If the result is research-only, record that no runtime changed and validate the evidence/plan without claiming unrun parity.
- [ ] 4.2 Reconcile the artifacts with what was actually retained and list evidence for every conditional decision. Verify no pending experiment is marked done by assumption and no unavailable phase mode is documented as shipped.

## Workflow follow-up

- `405` event decay depends on this change only if it needs a retained temporal comparator; other `405` work is independent.
- A research-only negative result can be finalized without new runtime code, but commit/push/archive still require an explicit request.
