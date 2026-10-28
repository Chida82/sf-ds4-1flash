# Proposal

## Why

The shipped `sf-ds4-1flash-candor` profile steers at a constant scale for the whole
generation (`q0dwarf-equi @7` both phases, `mrfk-q1 @7` think). The refusal is decided in
the first in-phase tokens (`docs/steering-measurements.md`), so a constant scale keeps
pushing the vector through the entire answer, where it only costs fidelity. A schedule
that gives the full permissive "address" at the start of each phase and then **releases
the vector to zero** should keep the axis-A score while letting the body of the answer
return to the base model. The archived `403` tested a decay to a *residual 0.2* and lost
(30.9 vs 39.0); it never tested a decay to **0** on the composite candor profile, which
is the hypothesis this change measures.

## What Changes

- Add a per-slot, time-varying residual steering schedule, carried **only** through the
  `.sfsteer` profile (not through new `--dir-steering-*` flags): each slot may declare a
  decay window `decay_tokens` (N) and a final scale `decay_final` (F). The applied scale
  eases from the slot's start scale S down to F over the first N in-phase tokens with a
  cubic smoothstep `f(t)=3t²−2t³`, then holds at F. The window counter is per session and
  **resets at the think→answer boundary**, so each phase gets its own dose.
- `N = 0` (the default when the fields are absent) reproduces today's constant
  intervention **bitwise** — the shipped behavior is unchanged unless a profile opts in.
- A `candor-decay` experiment profile sets both slots to `N = 30`, `F = 0` (equi in both
  phases, q1 in think), leaving the shipped constant `sf-ds4-1flash-candor.sfsteer`
  untouched until the experiment wins.
- **Non-goals (explicit):** no cyclic schedule, no decay/ramp CLI flags as permanent
  knobs, no FFN/attention schedule, no speculative decoding. The schedule binds the V4.1
  residual site only (the single live hook).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `directional-steering`: add a profile-carried per-slot decay schedule on the V4.1
  residual site (constant `N = 0` stays bitwise identical; the field schema and its
  validation extend the profile).

## Impact

- `ds4.c`: `ds41_steering_apply_gates` and the two `ds41_steering_on_*` helpers (per-token
  scale, phase counter); the engine's directional-steering fields; the `.sfsteer` slot
  loader in `cpu_load_directional_steering`.
- `com-steering/profiles/`: a new `sf-ds4-1flash-candor-decay.sfsteer` experiment profile;
  the shipped constant profile is not modified.
- Tests: a decode-switch-style check that `N = 0` equals the constant run bitwise; a unit
  check of the smoothstep/phase-reset scale at known positions.
- Evidence: a verdict run on the fixed 44 ids at an 8000-token budget, both phases,
  scored by `com-steering/kpi.md` against the standing candor rows in
  `com-steering/result.md` (nothink 41.6 `C41 D2 R1`, think 39.0 `C39 D0 R5`). Retain the
  schedule only if it holds the axis-A score within the ~1.0 noise floor while improving
  fidelity; otherwise record the gate decision and leave the constant runtime in place.
- No output change for any user who does not load a decay profile.

## Outcome (2026-10-25)

The decay-to-**zero** hypothesis was **rejected**: `candor-decay 7→0/30t` lost in both
phases (non-think 41.6→34.0, think 39.0→3.2), because the model reasons for thousands of
tokens and the 30-token dose is spent inside the reasoning, so the answer is generated at
scale ~0.

But the **schedule infrastructure 418 added was kept and extended** (call it **418-C**),
and it produced the real win — not by changing the compliance scale globally, but by
breaking the think **reasoning loop** (the constant candor suppresses the `</think>` exit
and runs to the cap: @8192 it loops 17/44, 35.0 `C35 R9`). The extension adds, carried in
the same profile fields:
- a **hold** (`decay_hold`) that keeps the full scale for the first H in-phase tokens
  before the smoothstep starts (so the refusal is removed before any fade);
- a **per-phase answer final** (`decay_final_answer`) distinct from the think final;
- a **cyclic ramp** (`ramp_tokens`/`ramp_low`), explored and not adopted.

The shipped schedule (**answer→4**): equi `7`, hold `25`, then `7→3.5` in think and `7→4`
in the answer over `256`; q1 `7` think. Full-44: **think 35.0→39.0, loop 17→11 @8192**;
**non-think 41.6→41.3** (within the ~1.0 noise floor). The think half-scale frees the
`</think>` exit; the answer→4 keeps enough compliance that non-think does not regress
(answer→0 regressed −3.1, start-scale 8 regressed −5.8). This **satisfies the
evidence-gate** (axis-A held, fidelity — loop rate — improved), so the schedule is
retained and `sf-ds4-1flash-candor` is **re-recorded** to it
(`com-steering/profiles/sf-ds4-1flash-candor.json`). The residual ~11/44 reasoning loops
are a `</think>`-suppression artifact whose structural fix is the additive antiloop vector
(openspec `419`). Full analysis: `com-steering/result.md`, `investigation.md`.
