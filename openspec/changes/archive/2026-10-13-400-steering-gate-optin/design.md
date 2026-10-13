# Design

## Context

See proposal.md for scope. The opt-in is already present in CLI/server options and the engine predicate. The default refusal was previously checked byte-for-byte; build and env-check success were reported. The 65-token state comparison and default-path parity remain unexecuted in the recorded work.

The former design incorrectly described legacy `metal_graph_*` steering hooks as live V4.1 hooks. V4.1 allocates `ds41_graph`; accepting a file alone does not activate those hooks. `401` owns application and errors for unsupported active sites.

## Goals / Non-Goals

**Goals:** finish a narrowly scoped admission change and leave repeatable evidence of unchanged default behavior.

**Non-Goals:** make FFN/attention steering work on V4.1, add steering to the bench, demonstrate refusal removal, or change cache compatibility.

## Decisions

### D1. CLI and server only

Keep the existing engine option shared by both frontends. Remove bench promises from these artifacts and future user-facing documentation, not the bench binary. Adding a bare opt-in to a frontend that cannot request steering serves no purpose.

### D2. Preserve presence semantics

The existing test is `getenv("DS4_ALLOW_V41_STEERING") != NULL`. Retain it to avoid an unrelated behavior change. Test unset, empty, `0`, and `1`; the latter three opt in. The CLI flag independently opts in. Tests must clear inherited variables explicitly so a developer's environment cannot bypass the default-refusal case.

### D3. Only one support-check term changes

The permission applies only to the steering-file clause. Test the supported single-box Metal configuration and at least one independently unsupported setting, such as power below 100, with the opt-in present. No error-message cleanup is part of this change. The final integration test may use `--dir-steering-residual 0` to isolate admission from the unsupported default FFN site addressed by `401`.

### D4. Separate evidence levels

- Model-less/frontend regression: option spelling, environment semantics and exact error text where an existing test seam can exercise them.
- Engine smoke check: the default rejection still exits 1; the opt-in clears only that condition.
- Model-backed no-op: opt-in without a file, then a file with explicit zero scales, versus baseline; 65 decoded steps with identical logits, KV and Engram. Reuse the existing graph-test comparison machinery.
- Default-path upstream parity: run separately on the final integrated build, without an opt-in.

If a case needs a model, label it model-backed rather than writing a mock that purports to prove engine behavior. A generated completion matching baseline is weaker evidence than a state comparison.

## Risks / Trade-offs

- [Ambient opt-in masks a regression] -> construct clean subprocess environments for negative cases.
- [Later `401` site validation changes a smoke command] -> use explicit residual scale zero for admission-only checks; retain the no-opt-in upstream refusal precedence.
- [A composite task hides unrun verification] -> track implementation, regression coverage and model-backed acceptance separately.

## Migration Plan

Keep option names and presence semantics. Update descriptions to admission-only and narrow the frontend list. There is no data migration. Disabling the flag and unsetting the environment variable restore the default gate.
