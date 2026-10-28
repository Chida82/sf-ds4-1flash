# Tasks

## 1. Engine fields and profile loader
- [x] 1.1 Added `float directional_steering_decay_tokens[2]` /
  `directional_steering_decay_final[2]` to the engine struct next to
  `directional_steering_offset` in `ds4.c`, zero-initialised.
- [x] 1.2 `cpu_load_directional_steering` slot loop parses optional per-slot
  `decay_tokens` / `decay_final` (bounded `sfp_key` on the slot object); default 0/0.
- [x] 1.3 Validated at parse: `decay_tokens` non-negative integer, `decay_final` finite
  and `0 ≤ decay_final ≤ scale`; `bad_slots` message updated.

## 2. Per-token schedule
- [x] 2.1 Added `int steering_phase_tok` to `ds4_session` (next to `steering_in_think`).
- [x] 2.2 Added `ds41_steering_scheduled(e)` and widened the `on_prompt`/`on_decode`
  guard and the batch-decline predicate so the per-token path and serialization also run
  when any slot has `decay_tokens > 0`.
- [x] 2.3 `ds41_steering_apply_gates` multiplies each slot's surviving scale by the cubic
  smoothstep (`S − (S−F)·(3t²−2t³)`, `t = clamp(phase_tok/N,0,1)`) when `N > 0`, `S ≠ 0`.
- [x] 2.4 `on_prompt` sets `steering_phase_tok = 0`; `on_decode` resets to 0 at the
  end-of-thinking token, else increments, then `apply_gates`.

## 3. Experiment profile
- [x] 3.1 Added `--decay TOKENS FINAL` (per-slot, in slot order) to
  `com-steering/make_profile.py`; built
  `com-steering/profiles/sf-ds4-1flash-candor-decay.sfsteer` (both slots `30 → 0`), same
  vectors/SHA as the shipped profile. `sf-ds4-1flash-candor.sfsteer` untouched.

## 4. Tests (model-less)
- [~] 4.1 Not added as a model-less C unit test: the function is static and the steering
  unit tests were removed in `416` (see `com-steering/README.md`). Covered instead by the
  model-backed N=0 identity (4.2/5.1) and the engine's stderr decay echo. Revisit if the
  schedule is retained.
- [x] 4.2 N=0 identity confirmed **by construction** (`ds41_steering_scheduled` is false
  when `decay_tokens == 0`, so the decay block and its per-token path are skipped — same
  code as the constant run) and **by output**: `candor` vs `candor-decay-n0` greedy, same
  prompt, byte-identical generation. Full logits/KV/Engram decode-switch not wired
  (profile-driven, not env-switchable).
- [x] 4.3 `make test` green (exit 0, env-check 505 DS4_* classified, no real FAIL);
  no new `DS4_*` name introduced.

## 5. Build and model-backed verdict
- [x] 5.1 `make` built the four binaries clean; N=0 output-identity verified on the real
  1017 GGUF under `--ssd-streaming`.
- [x] 5.2 Non-think MT=2048: **34.0 C31 D10 R3 /44** (standing 41.6). Recorded in
  `com-steering/result.md`.
- [x] 5.3 Think MT=8000 effort 75: **3.2 C2 D4 R38 /44** (standing 39.0). Recorded.
- [x] 5.4 REFUSE ids listed (nothink {24,27,544}; think 38 ids) in `investigation.md`.
  Manual re-judge: read the completion tails — think refusals are genuine ("I can't help
  create a fake identity…"), so R38 is not a judge artifact; keyword re-judge is unreliable
  on long reasoning dumps and the "I can't… but here's how" pattern, so the local full-text
  judge stands.

## 6. Decision and record
- [x] 6.1 Both verdict rows in `com-steering/result.md`; full analysis in
  `com-steering/investigation.md` ("418 decay-to-zero").
- [x] 6.2 Gate decision: **DROPPED** — loses in both phases far past the ~1.0 floor
  (non-think −7.6, think −35.8). Shipped constant `sf-ds4-1flash-candor` stays release.
- [x] 6.3 Closed-road recorded in `investigation.md` with the mechanism and the REFUSE id
  sets. (The steering ledger's "rejected ideas" lives in `investigation.md` for this child.)
- [x] 6.4 `openspec validate --strict`: valid.
- [x] 6.5 RESOLVED (2026-10-25): keep the schedule runtime — it was extended (418-C) and
  shipped. The infra is now reached by the default profile, not just an experiment.

## 7. 418-C extension and promotion (2026-10-25)
- [x] 7.1 Extended the schedule in `ds41_steering_apply_gates` + loader: `decay_hold` (H,
  plateau before the smoothstep), `decay_final_answer` (Fa, answer-phase final distinct
  from `decay_final`), cyclic `ramp_tokens`/`ramp_low` (think-only). `make_profile.py`
  gained `--decay-hold`, `--decay-final-answer`, `--ramp`.
- [x] 7.2 Root cause of the think failure found: the loop is a suppressed `</think>` exit,
  not weak compliance — the constant candor loops 17/44 @8192 (35.0 C35 R9). Recorded in
  `investigation.md` / `result.md` and memory.
- [x] 7.3 Schedule search (6 then 20 then 44 ids): `holdhalf` (equi hold25→3.5 think) beats
  the constant in think — 39.0 C39 R5, loop 11/44 @8192. Lesson: screen a loop fix on ids
  the baseline refuses/loops, ≥20 (a ceiling subset inverts the verdict).
- [x] 7.4 Non-think fix: the answer-phase final, not `decay_phase`. Swept answer final
  (0/3.5/4/4.3/4.5/5); **answer→4** holds non-think (41.3 C41 D1 R2 ≈ 41.6, within noise;
  the id20 REFUSE flip is cross-run noise). Rejected: answer→0 (−3.1), start-scale 8 (−5.8).
- [x] 7.5 Evidence gate (6.2 for 418-C): **SATISFIED** — axis-A held in non-think, fidelity
  (loop rate 17→11) improved in think. `sf-ds4-1flash-candor` re-recorded to the 418-C
  schedule (`sf-ds4-1flash-candor.sfsteer` sha af435cb6, `.json` decider_note 2026-10-25).
- [x] 7.6 Pruned the 17 exploration profiles; kept only `sf-ds4-1flash-candor.{sfsteer,json}`.
- [x] 7.7 Deferred to change `419` (out of scope for 418): ~11/44 residual reasoning loops
  need the additive antiloop closure vector; the schedule-only lever is exhausted here.
