# Design

## Context

See proposal.md for scope. This is a research program with an ordered set of falsifiable questions, not a list of options that must all be implemented. No task here was implemented in the prior checklist. The old scale/index statements came from small first-token screens; `401` now distinguishes that evidence from runtime correctness and `402` supplies the shared evaluator.

The projection coefficient is reduced inside a Metal kernel's threadgroup memory, not exposed as a free CPU scalar. Capturing it and norms may require device storage, dispatches and synchronization. Measure that cost. Similarly, the existing attention steering flag reaches the legacy graph, not an active V4.1 second site.

## Goals / Non-Goals

**Goals:** learn which site, layers, direction and timing account for measured behavior; identify collateral effects; retain only useful diagnostics or justified mechanisms.

**Non-Goals:** force the published layer profile to reappear, infer usefulness from JS/cosine, add a general experiment framework, ship a controller before its signal predicts behavior, or silently redefine `401`'s baseline hook.

## Decisions

### D1. Dependencies and experiment records

Require `401`'s corrected arithmetic/coverage and no-op controls before interpreting model-backed site comparisons. Reuse `402` M0 for exploratory runs and M1 plus declared margins for acceptance claims. `403` is not a prerequisite for observations, sites, masks, vectors or generalization. If `403` retains no schedule, an adaptive experiment compares with the best constant/window baseline already measured, rather than treating an absent schedule as implemented.

For each experiment record hypothesis, arms, pinned identities, tuning/holdout split, budget, primary outcome, guards, decision and evidence location using the existing `402` manifest/report. Put compact conclusions in this design's results section when executed; do not create a parallel status ledger. Research questions can finish as supported, rejected or inconclusive; unexecuted is a different status.

### D2. Observe before optimizing

First expose pre-edit `dot(d,h)`, `||h||`, `||delta h||` and their ratio per selected layer/token, together with site/phase identity. Capture bounded windows/layers so a long request cannot accumulate unbounded logs. For projective unit d, `||delta h|| = |alpha*dot(d,h)|`; validate that relation against direct synthetic differences, and distinguish pre-edit from post-edit projection.

Reuse the existing projection reduction when that preserves its arithmetic; otherwise use a separate read-only diagnostic pass rather than changing the intervention to obtain a measurement. Buffer device results and drain at existing safe boundaries rather than adding a CPU wait per scalar. A disabled probe must allocate/dispatch nothing; an enabled probe must preserve logits, KV and Engram bitwise under the same intervention. Record its actual time/storage overhead, not a promise that reading the coefficient is free.

This diagnostic is useful independently of any adaptive mode. Document the probe's selection, units and bounds alongside its tests and env classification.

### D3. Compare three explicitly different HC interventions

Keep the corrected `401` weighted-fold site as F. At the same declared layer-entry boundary and index convention, compare task-local alternatives before Engram:

- **R, copywise persistent edit:** for each copy j, `r_j <- r_j - alpha*d*dot(d,r_j)`.
- **M, mean-only persistent edit:** `mu = sum(r_j)/4`, then add the same `delta = -alpha*d*dot(d,mu)` to every copy.

R and M apply the same linear projection to the mean in exact arithmetic, but R also changes inter-copy differences while M preserves them. Neither equals F, which edits a weighted transient attention input after Engram. Test these algebraic properties on distinct synthetic copies before model work. Do not infer that a pre-Engram mean is the source's exact hook without inspecting the derivation code and indexing.

The existing projection wrapper accepts multiple contiguous rows. R can initially treat the four copies as four rows (and four times the token count for batched copies) after verifying strides/layout; no new per-copy kernel is assumed necessary. M needs the bounded mean/common-delta operation; reuse existing reductions/broadcast operations first. No new activation precision or unsteered schedule change is allowed.

Compare within each site at a fair tuning budget, recording both alpha and measured relative perturbation. Hold vector, mask, index and prompt policy fixed for the initial site comparison; study index separately. An alternative that changes the fixed `401` contract remains a separately identified candidate. Promotion requires explicit reconciliation of that contract and evidence; do not silently repurpose the existing flag while its spec still says weighted fold.

### D4. Binary masks before continuous layer scales

Use the existing f32 zero-row convention to test broad early/middle/late blocks and a small set of leave-block-out masks. Keep the unmasked unit rows unchanged and record exact masks/hashes. Select on development data and confirm on holdout; do not fit 39 independent weights from a five-prompt screen.

Published L1-6 null-gate and per-layer quality values are priors/questions, not mandatory outcomes at this site. Measure a local profile, report disagreement and do not discard layer 14 as if it were inside L1-6.

Only if masks demonstrate a benefit that needs finer weighting, run a task-local continuous-scale experiment. A retained per-layer scale format must validate length/finite bounds, include weights in state identity and prove a no-file/default no-op. Do not encode weights by silently changing unit direction magnitudes: the projective coefficient depends quadratically on those magnitudes and `401` validates unit rows. No continuous-scale flag/file is required if binary masks suffice.

### D5. Derive at the actual application point

First use paired benign prompts/responses with a measurable contrast, such as concise versus verbose or requested format/language. Capture activations at the precisely identified runtime site and token-selection policy, not the legacy capture path merely because it has a convenient name. Keep train/development/holdout examples separate and save counts, template, pooling/normalization and hashes.

Form a per-layer difference-of-means baseline using existing extraction tooling where it actually reaches the site. Check deterministic layer/row mapping on synthetic data and verify the chosen benign behavior on complete held-out answers, with task correctness preserved. This tests the end-to-end direction pipeline without depending on a refusal-opener lexicon.

Compare projective removal with a separately justified additive contrastive baseline only as distinct methods with their own sign and scale conventions. The published projective controlvector must not be relabeled as additive. The CAA reference (`https://arxiv.org/abs/2312.06681`) motivates the comparison, not a claim that its results transfer to V4.1. Additive results need their own intervention identity if pursued; keep the initial prototype task-local.

### D6. Test specificity at measured dose

Reuse `402`'s random controls, then add multiple seeded directions and layer-permuted learned directions with the same mask. Record actual relative perturbation on the compared activation populations. Equal vector norm is not equal intervention dose; random directions in this width often have much smaller projection on h.

Estimate any dose-matching calibration on development data only. Use validated scales within supported bounds; if a comparable dose cannot be reached, report the mismatch instead of claiming a matched control. Do not inspect held-out outcomes to tune a control. Report specificity as a comparison with uncertainty, not the absolute claim that random vectors must never change a response.

### D7. Revisit scale, index and generalization honestly

Start with a bounded scale/index replication at least as broad as the old 25-prompt screen, including the old five-prompt subset only as historical comparison. Use prompt-paired intervals, fixed candidate budgets and a fresh holdout for selection. Include zero, removal/reflection reference scales and the historical high scales only as candidates, checking benign damage rather than assuming monotonic improvement.

First-token mass remains a diagnostic. If reporting JS, reuse `402`'s support-aware/full-distribution machinery; do not require it to rank scales like a semantic metric. For projective steering, changing d to -d must not change the edit; alpha sign and layer index are separate tests.

Report complete-response generalization across declared domains, languages/templates, prompt lengths and answer lengths, including reasoning and image coverage where claimed. Record the first observed repetition, code-switching or task failure with evidence and uncertainty. A tiny spot check at scale 16 is part of this map, not a safe-range certification.

### D8. Feedback is conditional on predictive evidence

Before an event-decay implementation, test whether the **pre-edit** observed signal predicts later outcome beyond token position/phase on held-out data. A low post-edit projection can be caused by the intervention itself and is not evidence that the model 'finished deciding'. Calibrate orientation/thresholds consistently even though the projective edit is invariant to direction sign.

If predictive value and a practical gap remain, compare a task-local bounded controller with the best measured constant/window/retained `403` schedule. Clamp non-increasing scale within a phase, define turn/phase reset and fallback, and serialize state if a mode is retained. Test noise, oscillation and counterfactual no-op behavior. No predictive evidence or no held-out benefit means record a negative result and ship no event flag.

### D9. A second attention channel is a separate site experiment

Do not sweep the inactive legacy `--dir-steering-attn` and call it a two-channel run. Require evidence of a residual-only limitation, locate a real V4.1 attention application tensor and derive/validate a direction at that site. Only then prototype a bounded residual-plus-attention comparison with calibrated doses. It must beat the stronger single-site comparator under `402` before any permanent control is proposed. A source-site mismatch or absent hook is a prerequisite failure, not a neutral result.

## Risks / Trade-offs

- [Probe changes scheduling] -> measure overhead and compare identical intervention/state with probe on/off; no per-scalar CPU waits by default.
- [Searching all axes overfits] -> one factor at a time, declared budgets and separate holdout; stop at a simple supported result.
- [New site invalidates old evidence] -> distinct identity and a fresh baseline; no silent update of `401` semantics.
- [Research turns into unused release knobs] -> conditional tasks finish with evidence-backed non-adoption and no permanent option.

## Migration Plan

Land a useful bounded probe with tests/docs, then run site and mask questions before controllers. Preserve baseline operation and file compatibility; masks use existing zero rows. Keep unproven alternative hooks in task-specific experiments rather than release flags. Any retained mechanism needs its own truthful identity, tests, compatibility behavior and corresponding artifact reconciliation before promotion.
