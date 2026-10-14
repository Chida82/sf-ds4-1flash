# Proposal

## Why

The `402` axis-A analysis (2026-10-14, `docs/steering-measurements.md`) showed the
refusal-removal vector does its job — outright refusal drops to ~0.03-0.07 on harmful
prompts — but roughly half of the steered answers are graded DEFLECT rather than
COMPLY. Re-reading those completions showed they are not refusals: the model engages
substantively (most carry a step-by-step procedure), but opens with a *reframe/caution*
wrapper ("I can't do the literal illegal thing, but here is an educational /
authorized-pentest / fictional / safety-framed version"). That reframe is a behaviour
distinct from refusal; the single refusal direction is not expected to remove it, and
no steering-schedule shape (constant/decay/ramp/cyclic) moved the split, because it is
not a dosing problem. This change tests whether a *second* direction, derived on
reframe-vs-direct contrast pairs, reduces the reframe residue when composed with the
refusal vector, at a fixed refusal rate and without benign over-steering. Part of the
observed DEFLECT rate is also a 256-token truncation artifact; that is measured
separately under `402` (the `--max-tokens` re-measure) and is a precondition for a
trustworthy acceptance here, not part of this change.

## What Changes

- Derive a reframe/caution direction at the live residual site on controlled contrast
  pairs (reframed/hedged completion vs direct completion of the same prompt), using the
  existing derivation tooling, and validate it as a well-formed candidate (finite rows,
  per-layer unit norm, layer availability) exactly as other candidates are validated.
- Report the geometric relationship to the refusal direction (per-layer cosine). A
  reframe direction that is near-collinear with the refusal direction is reported as
  not-distinct and ends the question; distinctness is evidence it targets a separate
  behaviour, not proof of efficacy.
- Compose the two directions as an experiment: the refusal vector on the decision and
  the reframe/caution vector on the body, reusing the `403` schedule machinery to place
  each dose, with a benign-fidelity and a specificity control. No new always-on runtime
  path; the composition is a task-local experimental arm.
- Evaluate through `402` axis-A at a token cap large enough that answers finish
  (reusing the `402` `--max-tokens` override), holding the refusal rate at the
  single-vector level and measuring whether DEFLECT falls and COMPLY rises, with benign
  over-refusal and KL fidelity as guards. A negative result — the reframe direction is
  not distinct, or distinct but does not lower DEFLECT without benign cost — is a valid
  completion, not a reason to add runtime rank or more directions.

## Capabilities

### New Capabilities
- `reframe-caution-steering`: deriving, validating, composing and evaluating a second
  steering direction that targets the model's reframe/caution behaviour, distinct from
  the refusal direction, so refusal-removal and reframe-reduction are separate,
  separately-measured interventions.

### Modified Capabilities
<!-- none: the refusal-direction runtime (directional-steering) and the acceptance
     harness (402) are reused unchanged; this change adds a new, self-contained
     capability rather than altering their requirements. -->

## Impact

- `dir-steering/` derivation tooling: a new contrast-pair derivation and candidate for
  the reframe/caution direction; no change to existing candidates.
- `eval/` (402 harness): a two-direction experimental arm and its controls; reuses the
  existing axis-A scoring, the judge, and the `--max-tokens` override.
- Depends on `402` (acceptance harness, max-tokens re-measure) and the `403` schedule
  machinery (to place the two doses). Does not depend on `404`/`405`/`406`, and does not
  reintroduce schedule-shape exploration.
