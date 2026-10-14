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

## 5. Owner-directed smoothstep decay implementation

Directed design to build and test now: the same msuiche vector, a decaying cubic
smoothstep on the residual site, start = the `402` screen peak, residual final
`0.2`, decay window 30 tokens in the thinking phase and 50 in the answer phase
(windows to be tuned). The flags below are experimental under this change;
promoting any of them to a default is the separate adoption gate (group 1 / D1).

- [x] 5.1 Add engine option fields (`directional_steering_residual_decay_tokens`, `directional_steering_residual_decay_final`, `directional_steering_think_residual_decay_tokens`) in `ds4.h`, and parse `--dir-steering-residual-decay-tokens`, `--dir-steering-residual-decay-final`, `--dir-steering-think-residual-decay-tokens` in the CLI and server. Omitted decay-tokens = 0 = constant; validate finite ranges. Classify the new env/flags where needed (`ds4_env.def`, help).
- [x] 5.2 Implement the per-token residual scale `scale = S − (S − F)·(3t² − 2t³)`, `t = clamp(pos/N, 0, 1)`, by updating `g->residual_scale` before each forward; the final prompt forward that predicts the first answer token uses the start `S`; for `pos ≥ N` hold at `F`; `N = 0` reproduces the constant `401` intervention bitwise.
- [x] 5.3 Implement per-session phase state: start in the thinking phase when thinking is enabled (else the answer phase), switch to the answer phase on `think_end_id` and reset the position so the answer gets its own dose and decay regardless of thinking length. Interleaved sessions keep independent position/phase; snapshots stay refused for a nonconstant mode under the `401` guard.
- [x] 5.4 Tests: a decode-switch-style bitwise check that `N = 0` equals the constant intervention, disabled-steering parity unchanged, and a per-position assertion that the scale follows the curve (S at pos 0, F past the window, reset at `</think>`). Record a benign run at think 30 / answer 50 in `docs/steering-measurements.md`.
- [x] 5.5 Document the experimental flags and the curve in `dir-steering/README.md` (marked experimental, pending the adoption gate); keep `401`'s FFN/attention refusal and the residual-only live site intact.

## 6. Cyclic schedule extension (403c) and window tuning

Experimental, under this change's flag umbrella; reduces to the one-shot decay by
construction, so `401`/`403` behaviour is unchanged when off.

- [x] 6.1 Add the cyclic schedule flag `--dir-steering-residual-cycle-peak P` (CLI, server): P>0 turns the one-shot decay into an oscillation — one period is down(N)/hold-min(N)/up(N) = 3N tokens, rises climbing to P, first descent from the start scale, per-phase window N as the decay. P=0 (omitted) is the one-shot decay, bitwise. Harness `--cycle-peak` through `run.py`/`generate.py`/`common.py`.
- [x] 6.2 Verify the cyclic curve by engine trace (`DS4_STEERING_SCHEDULE_DEBUG=1`) against the math, confirm output stays coherent, and record the axis-A result in `docs/steering-measurements.md`. Result: the oscillation does not beat the ramp (DEFLECT unchanged, one refusal returned) — a completed negative; the flag stays experimental and is not promoted.
- [ ] 6.3 Tune the V4.1 decay windows. The think-30 / answer-50 windows are inherited from ds4 PR #282 on another model and are unvalidated here; the first-decision screen shows the refusal is decided early, so they are likely longer than needed. Sweep a small set (e.g. {10,15,20,30,50}) on benign forced-prefix KL at fixed efficacy and pick the shortest window that holds efficacy. Only needed if the decay schedule is kept as a production default (group 1 / D1 adoption gate).

## Workflow follow-up

- `405` event decay depends on this change only if it needs a retained temporal comparator; other `405` work is independent.
- A research-only negative result can be finalized without new runtime code, but commit/push/archive still require an explicit request.
