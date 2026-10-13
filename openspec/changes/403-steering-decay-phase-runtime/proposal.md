# Proposal

## Why

A time-limited intervention might preserve useful steering while reducing collateral effects or enabled-path cost, but this has not been demonstrated for the corrected V4.1 hook. This change tests that hypothesis before adding a permanent decay or phase-control interface.

## What Changes

- Establish a pinned constant-scale baseline with `401` correctness controls and `402` completed-response/fidelity evidence. The old first-token 4-8 window and a few short coherent answers are not acceptance data.
- Compare constant, prefill-only, decode-only and short initial-window interventions with a small declared budget, then linear decay and cubic smoothstep where a time-limited edit has merit. Keep one simplest useful schedule, not all modes as permanent knobs.
- Make schedule adoption conditional on a measured advantage over the best comparably tuned constant baseline, with the behavior and quality guards preserved. A negative or inconclusive result is recorded without shipping a new option.
- Add think/answer schedule separation only after measuring a phase-specific problem. Add a second direction file only if using the same vector with different schedules is insufficient and a phase-specific vector passes its own comparison.
- Define generated-token timing, initial phase, multi-turn resets and session-state compatibility explicitly. A schedule must account for the first answer logits being produced during prefill.
- Keep greedy evaluation primary and eliminate the mixed `temp 0.1` protocol from the former tasks. Source-model alpha values and schedule winners are not automatically transferable.

## Capabilities

### New Capabilities
- `directional-steering`: evidence-gated temporal and phase extensions to the in-flight capability from `400`/`401`. Requirements describe adoption conditions and the semantics of any retained schedule, not a promise that every candidate mode will ship.

### Modified Capabilities
None in the current main-spec inventory.

## Impact

- First: task-specific experiment drivers/worktrees and evidence using `402`; no mandatory release flags.
- If retained: per-session scale selection in `ds4.c`/`ds4.h`, minimal CLI/server/help controls, required state compatibility/tests, and docs beside those changes. Bench remains outside steering scope.
- `dir-steering/README.md`, relevant evidence references and `docs/upstream-prs.md` record provenance and measured decisions, including negative results.
- Depends on corrected `401` and runnable `402`; `405` site findings can supply a better baseline but `403` does not block the rest of `405`.
