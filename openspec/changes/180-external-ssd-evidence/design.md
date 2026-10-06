# Design

## Context

See proposal.md.

With `DS4_METAL_PREFILL_REPLICA` unset, `140`'s code still runs:
- `has_replica` tests at engine open;
- the per-worker family selection in `ds41_prefill_expert_read` (`n_up = 0`);
- the per-layer byte counters;
- the `has_replica` test at each `ds41_prefill_expert_read_start`.

Decode is untouched (`145` dropped its decode use).

The expected cost is about zero, but the owner's threshold, 0.1%, is below what one A/B invocation resolves.

## Goals / Non-Goals

**Goals:** a measured bound on the no-drive overhead, and a README comparison a user can act on.

**Non-Goals:**
- New runtime features.
- Other drives or enclosures.
- A one-shot CLI startup comparison beyond the `140` break-even already recorded.

## Decisions

### D1. Overhead A/B

- **A** is a worktree of `main` with the replica code reverted by hand to its pre-`140` form, keeping every later change. It is built only for this measurement.
- **B** is `main`.
- Neither arm sets the variable.
- Kinds: `cold,append,decode`, `--bitwise`. Pool invocations until each target metric's 95% CI half-width is at most 0.15%, or three invocations, whichever comes first.
- **Accepted** when no throughput metric's pooled CI lower bound is below -0.1%.
- **Rejected** when a pooled CI lies wholly below -0.1%. Then locate the cost (for example the family loop) and remove it, as a step of this change.
- **Inconclusive** after three invocations: report the median and the CI to the owner.

### D2. With and without the drive

- One run of A/B kinds `cold,append,decode` plus the guards, with A = `main` without the variable and B = `main` with `--b-env DS4_METAL_PREFILL_REPLICA=<copy>`. The `140` numbers re-measured on the current tree.
- The README table states, per metric, the internal-only figure, the with-drive figure and the gain, plus the hardware, the cache flag and the date. It links to the record.
- The KV cache placement is not part of the harness. Its measured cost (`160`) is quoted, not re-run.

## Risks / Trade-offs

- [A 0.1% bound needs many pairs; heat drops pairs] -> night runs, pooled invocations, and an inconclusive verdict reported rather than forced.
- [The hand revert in A drifts from `140`'s actual pre-change code] -> diff A against `67b75b8`'s replica-free functions and record the diff summary.
