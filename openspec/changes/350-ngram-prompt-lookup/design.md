# Design

## Context

- **#1167** proposes, for V4 Flash, the most recent earlier match of the last three tokens and up to N following tokens. Its drafts go through the DSpark verifier, its commit and rollback, and its back-off. Width 5 is recommended, because it matches the verifier's slots.
- **Upstream's verifier is not bitwise.** #1167 says so itself: long greedy continuations with drafting can diverge from target-only decode, because of the verifier's reduction order. In this child, `320`'s D2 rows kernels remove that, so the lookup inherits identical output.
- **The verifier** is `320`'s, or this change's own if it runs first.

## Goals / Non-Goals

**Goals:**
- A gain on copy-heavy agent work with zero memory.
- The verifier and rollback brought in early, if `310` chooses this path.

**Non-Goals:**
- Lookup in other sessions or on disk; suffix trees.

## Decisions

### D1. The longer proposal wins
- **The rule.** Per cycle, the source whose proposal is longer is verified: lookup matches are long or absent, DSpark's are confidence-cut. On ties, DSpark wins, because its confidence predicts acceptance.
- **The rejected alternative.** Verifying both in one pass doubles the rows and the expert union for one accepted prefix.

### D2. Lookup on the token history the session already keeps
- **Where it searches.** The session's token history; there is no new index.
- **Why a scan is enough.** One backward scan per cycle over at most the context is microseconds against a ~34 ms token. A suffix array is the upgrade, if a profile ever shows the scan.

### D3. When this change runs first
- **What it carries.** `320`'s verifier, rollback, rows test, streaming rows (D3 of `320`) and harness tool step, with this source instead of DSpark's.
- **What then changes in `320`.** It shrinks to the support file, the drafter and the combination rule here.
- **Renumbering.** This change is renumbered below `320` when the decision is made, keeping the "numbered in execution order" rule.

## Risks / Trade-offs

- **[Prose pays for empty lookups]** → No match means no proposal and no verify. Only matches that fail cost a cycle, and back-off covers them.
- **[A long wrong match costs a full-width verify]** → The cap is the verifier's, and `310`'s c(k) sets it.
