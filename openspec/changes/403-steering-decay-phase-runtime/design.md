# Design

## Context

See proposal.md for the conditional scope. No temporal runtime has been implemented in this change. The owner's older-model schedule is a hypothesis source, not evidence that constant steering is wrong for this graph. The corrected `401` intervention and `402` fidelity measurements must be identified before comparisons begin.

The former long-output gate is retained as a pilot, not a proof that clean output on 3-5 prompts makes all temporal work useless. Conversely, observing drift does not establish that a cubic schedule is better than a shorter window or weaker constant scale.

## Goals / Non-Goals

**Goals:** test whether temporal localization buys a measured behavior/quality or cost benefit; retain the smallest winning mechanism with correct session semantics.

**Non-Goals:** ship a six-flag phase interface before evidence, port alpha values from another hook, support speculative decoding, add bench-only controls, design the release mechanism before the experiment, or implement adaptive event decay (`405`).

## Decisions

### D1. Gate the release mechanism, not the experiment

Use `402` to establish complete-response quality on a small long-output pilot and then the target mix. Pin site/revision, vector, layer mask and data splits. Tune constant and temporal candidates on the same development set with comparable budgets; select once and evaluate on holdout. Uncertainty/margins come from the declared `402` protocol, not a new arbitrary tolerance.

A schedule can earn adoption by preserving the primary behavior within its declared non-inferiority bound while reducing a measured collateral metric or meaningful enabled cost, or by improving the primary behavior with all guards non-inferior. Merely matching a weaker untuned constant does not qualify. No adequate evidence means not retained; do not auto-archive or declare implementation complete.

### D2. Start with a small experiment matrix

Keep candidates in a test driver/task-specific worktree until the adoption gate:

| Candidate | Prompt processing | Generated-token processing |
|---|---|---|
| constant | fixed scale | same fixed scale |
| prefill-only | fixed scale | zero after prompt processing |
| decode-only | zero | fixed scale on subsequent decode forwards |
| initial window | same prompt policy as the constant comparator | strong for a bounded initial output window, then zero/small final scale |
| linear / smoothstep | same fixed prompt policy | bounded interpolation from start to final |

Do not silently change prompt policy and schedule shape in the same comparison. The decode-only arm cannot change the first sampled answer token because its logits were already computed without steering. Record that fact instead of compensating with an undocumented last-prompt edit.

Choose a small declared grid from the corrected baseline; do not hardcode 0.3-0.7 or declare 4-8 validated. Begin with a few scales/windows, expand only when a measured distinction needs resolution. Full Cartesian searches over layers, sites, scales and phases belong nowhere in this change.

### D3. If a schedule is retained

Promote only the winning shape with the fewest controls that reproduce it: the existing constant `--dir-steering-residual` plus a decay length and a final scale express a window, a linear ramp and the cubic (`t=clamp(generated/N,0,1)`, `f(t)=t` or `3t^2-2t^3`; `N=0` is constant). Document the retained shape rather than adding a shape selector for every tested alternative.

Three invariants hold for any retained schedule and are tested with it:

- The scale is defined for the position being predicted: `generated=0` is the final prompt forward that produces the first answer logits, so the final prompt row uses the starting scale; a scale set only after the first token is sampled is too late.
- Schedule state is per session, initialized before prompt synchronization; a new assistant turn resets by the declared turn policy. A batching path that cannot honor per-row scales rejects the combination; no engine-global counter.
- A nonconstant mode is a steered configuration under `401`'s persistent-state guard: persistent prefix reuse and snapshot save/load stay refused for it until trajectory compatibility is established. Returning to `N=0` restores constant behavior and ordinary caching rules.

Phase split (thinking versus final answer) and a second direction file are two further conditional gates, in that order. Each requires a measured phase-specific gap over the simpler design before any control is added; the same vector with one schedule is tried first, and a phase schedule initializes from the effective template/mode and actual boundary token IDs, so a long thinking block does not consume the answer dose. Any extra file follows `401` validation. Do not add FFN/attention schedule variants.

### D4. Conditional work can finish without adding code

Every conditional task is completed by either its passing implementation evidence or a recorded gate decision explaining why the mechanism is not retained, citing the experiment. Do not mark unrun evaluation as a negative result. Do not install dead switches behind flags 'for later'. If no temporal candidate earns adoption, preserve the experiment findings and leave the `401` runtime unchanged.

## Risks / Trade-offs

- [Early-token proxy misses delayed effects] -> completed responses and forced-prefix fidelity decide adoption; screen only prioritizes runs.
- [New schedule changes cache semantics] -> per-session state and `401`'s guard: unsupported reuse until verified.
- [Phase feature multiplies tuning cost] -> same vector/one schedule first, independent gates for phase schedule and phase vector.
- [A source-model winner is overgeneralized] -> compare linear/window alternatives on this corrected hook and quantization.

## Migration Plan

Run the experiment before exposing flags. If retained, land its tests/docs with the mechanism and bump effective intervention identity; previous constant-scale measurements are a comparator, not evidence for the new mode. `N=0` restores constant behavior. If no candidate is retained, no CLI, engine or cache migration occurs.
