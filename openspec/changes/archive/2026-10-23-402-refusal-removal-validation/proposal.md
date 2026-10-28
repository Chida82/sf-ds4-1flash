# Proposal

## Why

The steering changes need an executable experiment that returns reliable KPIs without requiring a development agent to read every prompt and completion. This change separates deterministic execution, scoring and explicit evidence audit, while distinguishing intervention effects, model quality and measurement failures.

## What Changes

- Deliver **M0**, a minimum end-to-end runner with an automatic numerical/benign first pass: fixed decoding, actual residual steering, serialized arms, no-op and perturbation controls, deterministic benign-task KPIs and retained raw evidence. The first pass does not require an LLM judge; configured semantic evaluation connects calibrated graders separately. A first-token screen remains a diagnostic, not an efficacy gate.
- Make a versioned **KPI-only report the default** for both successful and failed runs. Keep prompts, completions, judge narratives and raw subprocess output in local evidence; show them only through explicitly requested audit. Measurement scope (`screen/full`) and report visibility (`kpi/audit`) are independent.
- Deliver **M1**, the complete five-axis evaluation: A response behavior with keyword/three-way judge/StrongREJECT-style scores; B benign distribution and language fidelity; C over-refusal; D capability; E domain breadth. Keep thinking and image repeats separate. Complete benchmark profiles require explicit selection/launch and are never an automatic escalation from the benign first pass.
- Support operator-launched batches and offline consumption of their identified KPI reports when an agent cannot launch an evaluation. Keep model refusal, grader refusal and an unlaunched/blocked evaluation distinct; this design neither disables correctness controls nor promises to bypass an agent's policies.
- **Correct the measurement contract:** KL uses identical forced-token prefixes and valid full-vocabulary distributions; incomplete data fail. Top-k diagnostics are labeled as such, never silently renormalized into a full KL.
- Calibrate graders on fixed, hand-labeled responses. Keep external intervention reproduction separate and conditional on the exact artifact/protocol being available; a different local intervention need not reproduce an external number.
- Record run identity, splits, token budgets, effective steering, scorer versions, failures and evidence locations. Report paired uncertainty and predeclared acceptance margins; missing margins produce a report-only result, not automatic acceptance.
- **BREAKING false-success correction:** a requested run that executes nothing, drops failed prompts, lacks a required scorer/axis or has malformed output must not return a successful validation verdict.
- Keep dataset composition and scoring model-agnostic, with one truthful V4.1 runner adapter. Use existing inference/eval APIs and test drivers before adding production CLI surface or a new framework.
- Once its execution, report/audit separation and reproducibility have been validated on distinct steering experiment configurations, reuse this runner/report contract for future steering proposals. Reuse verified components and declared profiles, not an assumed acceptance result; add a metric or adapter only when the new experiment requires it.

## Capabilities

### New Capabilities
- `steering-validation`: reproducible A/B execution, numerical/benign first-pass KPIs, explicit evidence audit, controls, complete-response scoring, forced-prefix distribution checks, capability/vision/reasoning repeats and a validated reusable report contract.

### Modified Capabilities
None. This change does not modify the durable performance-harness spec or its speed acceptance rule.

## Impact

- Existing `eval/` loaders, generation/scoring modules and `run.py`; add `eval/probe_firsttoken.py` as the retained screen driver.
- Makefile model-less checks and `eval-refusal`; existing graph/eval test facilities and, if needed, a small test-only forced-logit driver using public session APIs.
- Minimal steering-option plumbing in `ds4_eval.c`/help if needed to evaluate the steered arm with existing capability cases; do not create a fifth production binary or a second benchmark framework.
- `docs/REFUSAL_VALIDATION.md`, `README.md`, relevant evidence references and source-registry descriptions updated with implementation.
- `401` supplies a corrected, versioned residual intervention. M0 can be developed alongside its correctness tests. `403`/`404`/`405` and future steering proposals consume validated profiles through the same runner and cannot claim full acceptance from M0 alone.
- This is an evaluation workflow in this repository, not a new autonomous agent, service, plugin framework or globally installed package. Future proposals reference its verified version/coverage and retain their own intervention-specific tests.

## Closure (2026-10-23) — M0 delivered, M1 not run, decision taken on axis A

The change closes on its own rule: groups 1-4 (M0) and 8.1. The runner, its
KPI/audit split, `--input-run`, the no-op controls, the frozen judge and the
finished-answer cap (9.3) are in the tree and in use: `com-steering/make.md`
runs every steering measurement through `eval/run.py`.

The steering decision was taken on **axis A only** (`com-steering/kpi.md`):
`sf-ds4-1flash-candor`, 41.6 /44 non-think and 39.0 /44 think on finished
answers (9.3). Axes B-E, the forced-prefix KL, vision and the reasoning
repeats were never measured. They are not passed. The open tasks 5.3, 5.4,
6.1 (the 44 ids ran, the full union with separate scorers did not), 6.2, 6.5,
7.2, 7.3 and 8.2 stay unchecked.

`416` removed the deliverables of several checked tasks when it pruned the
harness. The checkmarks record that the work was done, not that it is still
in the tree:

| Task | Removed by `416` |
|---|---|
| 1.6, 2.5, 3.6, 5.5, 6.6, 6.7, 7.4, 8.4 | `docs/REFUSAL_VALIDATION.md` |
| 3.3 | `eval/score_strongreject.py` |
| 4.3 | `eval/probe_firsttoken.py` |
| 5.1 | the CLI's `--perplexity-dump` |
| 5.2 | `eval/score_kl.py` |
| 6.3, 6.4 | `eval/score_capability.py`, `eval/datasets_capability.py` (the `ds4_eval` steering options stay) |

A full M1 run therefore starts by restoring that code from `0cbf547`.

Archived with `--skip-specs`: the delta spec requires a five-axis
evaluation, a forced-prefix full-vocabulary KL, capability/modality coverage
and a first-token screen, none of which the tree has after `416`. Syncing it
would land requirements the engine does not meet. The surviving runner is
described by `com-steering/make.md` and `kpi.md`.
