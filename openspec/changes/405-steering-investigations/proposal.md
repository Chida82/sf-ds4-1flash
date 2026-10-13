# Proposal

## Why

The current steering evidence cannot yet distinguish a good direction, a suitable HC site and a large generic perturbation. This change orders the investigations so that instrumentation and causal comparisons precede new runtime controls, and a negative result can finish a question without adding a feature.

## What Changes

- Add bounded, read-only observations of projection and activation/intervention norms, with measured overhead and an unchanged off path.
- Compare the corrected weighted-fold baseline with task-local persistent-residual interventions: project each HC copy, or edit only their mean while preserving copy differences. These are explicitly different sites/operations, not silent replacements for `401`.
- Test simple layer masks by zeroing rows in the existing f32 format before considering a separate continuous per-layer scale interface.
- Derive directions at the actual runtime site on controlled benign contrast pairs and compare appropriately derived additive versus projective interventions as experiments, not interchangeable consumers of an external vector.
- Strengthen specificity controls with multiple seeds, layer permutations and measured activation-dose matching; re-examine scale/index claims with paired uncertainty rather than requiring the old conclusions to hold.
- Map generalization and failure modes on held-out domains, languages, templates and output lengths. Complete responses and quality guards decide usefulness; distribution shift alone does not.
- Make event-based decay and a second attention site conditional, task-local experiments. Only event decay needs a temporal comparator from `403`; the rest of this change does not depend on it.

## Capabilities

### New Capabilities
- `directional-steering`: observable intervention diagnostics and evidence-gated experiment contracts extending in-flight `400`/`401`. Alternative mechanisms are research candidates, not promised permanent flags.

### Modified Capabilities
None in the current main-spec inventory.

## Impact

- `ds4.c`, `ds4_metal.m`/existing kernels and graph tests only for bounded probes or explicitly gated experiment hooks; preserve the normal path and avoid unused release variants.
- Existing `dir-steering/` tools for masks and locally captured directions; reuse `402` execution, metrics and manifests.
- Results in this change's design/evidence references, appropriate `dir-steering` docs and provenance registry entries; performance records only for actual performance measurements.
- Depends on corrected `401` and the applicable `402` milestones. `403` is a dependency only for experiments that compare against a retained temporal schedule.
- No automatic promotion of an alternative site into the `401` baseline, no rank-2/3 runtime implementation, no mandatory new scale file or attention control.
