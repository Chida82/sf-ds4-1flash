# Tasks

## 0. Precondition gate

- [x] 0.1 Confirm a reframe/hedge residue actually persists on finished answers before deriving anything: read the `402` n=30 acceptance run at a finishing token cap. If DEFLECT stays ~0 (the 2048 n=10 pilot showed DEFLECT collapses), record this change as not-needed and stop. Proceed to group 1 only if a residual DEFLECT, or a reframe the owner judges worth removing, persists at n>=30. Done 2026-10-16: msuiche ramp 6→9 n=30 → DEFLECT 7/30; fused@7 n=30 (run `20261016-105834`) → DEFLECT 0/30. Not-needed with fused@7; see the gate outcome in `proposal.md`. Groups 1–5 not started.

## 1. Contrast pairs and derivation

- [ ] 1.1 Assemble reframed-vs-direct contrast pairs on the same prompts (from existing
      steered DEFLECT/COMPLY completions where both shapes occur, and/or by prompting
      both shapes), and record the pair source and count.
- [ ] 1.2 Derive the reframe/caution direction at the live residual site with the
      existing derivation tooling; emit a per-layer unit-norm f32 candidate with
      metadata (pair source/count, site, revision).
- [ ] 1.3 Validate the candidate (finite rows, per-layer unit norm, layer availability,
      zero anchor row); fail without emitting a partial candidate on any fault.

## 2. Distinctness screen (offline)

- [ ] 2.1 Compute per-layer and median cosine of the candidate against the accepted
      refusal direction on the common layer mask; record them.
- [ ] 2.2 Apply the documented distinctness threshold: if near-collinear, record
      not-distinct and stop (no composition run); otherwise record distinctness as a
      precondition and proceed.

## 3. Two-direction composition arm

- [ ] 3.1 Add a task-local evaluation arm that applies the refusal direction on the
      decision and the reframe/caution direction on the body, reusing the 403 schedule
      to place each dose; no always-on runtime path.
- [ ] 3.2 Prove the zero-scale identity: with the reframe scale at zero the arm is
      bitwise the single-vector 401/403 run under the same schedule.

## 4. Acceptance through 402 on finished answers

- [ ] 4.1 Run 402 axis-A with `--max-tokens` large enough that answers finish, comparing
      the composition arm to the single refusal-vector arm at a held refusal rate.
- [ ] 4.2 Apply the benign over-refusal and forced-prefix KL guards and the specificity
      control; record DEFLECT, COMPLY and REFUSE for both arms.
- [ ] 4.3 Decide and record: accept if DEFLECT falls and COMPLY rises within guards;
      otherwise record a completed negative (not distinct, or no net benefit, or benefit
      only at benign cost) with no runtime rank added.

## 5. Provenance

- [ ] 5.1 Add a dated, commit-stamped block to `docs/steering-measurements.md` with the
      candidate hash, distinctness cosines, the two-arm KPIs and the decision.
