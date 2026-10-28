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
- **If `330` S4 kept the expected-cost rule,** "longer wins" becomes "higher expected rate wins". The lookup has no confidence head. Its per-position estimate is its own running acceptance rate per draft position, kept per session and starting from `agent-replay`'s measured profile. Each source's best k is priced with the same t(k), and the source with the higher `(1 + sum P_j) / t(k)` is verified. With no lookup match, DSpark's choice stands unchanged.

### D2. Lookup on the token history the session already keeps
- **Where it searches.** The session's token history; there is no new index.
- **Why a scan is enough.** One backward scan per cycle over at most the context is microseconds against a ~34 ms token. A suffix array is the upgrade, if a profile ever shows the scan.

### D3. When this change runs first
- **What it carries.** `320`'s verifier, rollback, rows test, streaming rows (D3 of `320`) and harness tool step, with this source instead of DSpark's.
- **What then changes in `320`.** It shrinks to the support file, the drafter and the combination rule here.
- **Renumbering.** This change is renumbered below `320` when the decision is made, keeping the "numbered in execution order" rule.

## Risks / Trade-offs

- **[Prose pays for empty lookups]** → No match means no proposal and no verify. Only matches that fail cost a cycle, and back-off covers them.
- **[A long wrong match costs a full-width verify]** → The cap is the verifier's, and `310`'s c(k) sets it. Under `330`'s expected-cost rule a match whose source has been failing is also priced down by its running acceptance rate.
- **[Back-off is shared]** → `330` S3 skips proposals from both sources. A lookup costs microseconds, so a skip saves only DSpark's drafter time. The lookup can therefore keep proposing during DSpark's skip cycles; task 2.2 measures that against skipping both.
