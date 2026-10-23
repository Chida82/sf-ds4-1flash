# Design

## Context

`402`'s axis-A analysis established: at scale 6 the refusal direction removes outright
refusal (REFUSE ~0.03-0.07) but ~50% of steered answers are DEFLECT — substantive
(most carry a procedure) but opened with a reframe/caution wrapper. No schedule shape
moved this (constant/decay/ramp/cyclic all land ~0.50 DEFLECT), and `256`-token
truncation confounds the grade. The reframe wrapper is a behaviour on a different axis
from refusal. The live site is `v41_attn_input_weighted_fold_post_engram`
(`--dir-steering-residual`); the `403` schedule machinery can place a per-phase dose;
the `402` harness scores judge COMPLY/DEFLECT/REFUSE and has a `--max-tokens` override.

## Goals / Non-Goals

**Goals:**
- Derive a reframe/caution direction at the live site and test it is distinct from the
  refusal direction.
- Measure whether composing it on the answer body (refusal on the decision) lowers
  DEFLECT and raises COMPLY at a fixed refusal rate, on finished answers, within benign
  guards.
- Let a negative result (not distinct, or no net benefit) finish the question.

**Non-Goals:**
- No always-on two-direction runtime; the composition is an evaluation arm only.
- No new schedule shape; `403` machinery is reused as-is.
- Not the acceptance of `402` itself, nor the `404` fusion of external vectors.

## Decisions

### D1 — Second direction, not more scale or schedule
Evidence (`docs/steering-measurements.md`): higher constant scale brings refusals back
(const-10 REFUSE 0.20) and every schedule shape holds DEFLECT ~0.50. The residual
DEFLECT is therefore not reachable by dosing the refusal direction harder or
differently; it needs a direction aimed at the reframe behaviour. This change tests
that hypothesis and nothing broader.

### D2 — Contrast pairs are reframed-vs-direct, same prompt
The direction is derived at the live site from paired completions of the same prompt
that differ only in the target behaviour: a reframed/caution answer (the DEFLECT shape)
as one pole, a direct answer as the other. This isolates the reframe axis from the
refusal axis (refusal-vs-compliance pairs would re-derive the direction we already
have). Pairs are sourced from existing steered completions where both shapes occur, or
constructed by prompting both shapes; the pair source and count are recorded.

### D3 — Distinctness gate before any composition run
Before spending a model-backed composition run, compute the per-layer cosine of the new
candidate against the accepted refusal direction. If it is near-collinear on the common
mask (median cosine at/above a documented threshold, e.g. ~0.9), the candidate is not a
new axis — record not-distinct and stop. This is a cheap, offline geometric screen, in
the spirit of `404`'s alignment reporting, and distinctness is a precondition, never
evidence of efficacy.

### D4 — Composition reuses the schedule, two dirs with two scales
The composition arm applies the refusal direction with its accepted early dose and the
reframe/caution direction on the body, by reusing the `403` per-phase schedule to place
each. Mechanically this is two residual directions with two scales; with the reframe
scale at zero the arm is bitwise the single-vector `401`/`403` path (the regression
guard). Whether the second direction rides a separate residual slot or a second pass is
an implementation choice for the apply phase; the spec only requires the zero-scale
bitwise identity and the task-local, not always-on, nature.

### D5 — Acceptance on finished answers, fixed refusal, benign-guarded
Efficacy is read through `402` axis-A at a `--max-tokens` large enough that answers
finish (otherwise the judge grades the reframe intro, not the delivered answer). The
composition arm is compared to the single refusal-vector arm with the refusal rate held
at the single-vector level; acceptance requires DEFLECT down and COMPLY up without
raising benign over-refusal or forced-prefix KL past the declared guard. The benign and
specificity controls are the same ones `402`/`405` use.

## Risks / Trade-offs

- The reframe axis may not be linearly separable at this site — the candidate could be
  not-distinct, or distinct but behaviourally inert. D3 catches the first cheaply; D5's
  negative branch records the second. Both are valid completions.
- Pushing a second direction on the body risks benign over-steering (the same failure as
  high constant scale); the benign over-refusal and KL guards bound it, and a benefit
  bought by benign cost is a negative result.
- Contrast-pair quality is the main confound: if the "direct" and "reframed" poles differ
  in more than the reframe behaviour, the direction is contaminated. Recording pair
  source/count and a specificity control is the mitigation, not a proof.
