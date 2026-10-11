# Design

## Context

- `320` has landed. The facts below come from its section and from `310`'s:
  - c(k) in the child;
  - the miss share of a verify cycle;
  - prose under back-off;
  - the memory timeline with the drafter beside `82GB`.
- **The automatic budget** is computed in `ds4_engine_configure_streaming_cache_budget` (86% of the recommended working set). It knows the context buffers and the prefill reserve, not the drafter.
- **`170`** closed route-prediction prefetch for decode: the guess costs about 0.3 ms per token, more than the third of the hideable miss time that the drives could sustain. Decode misses are read by the reader pool and split across both drives (`145`, `260`).
- **#1168** (V4 Flash) doubles the pause on consecutive rejected proposals (2..64 cycles), leaves the first miss unpunished, and spends earned credit on isolated misses. #1073's `ds41_draft_adapt` instead compares smoothed tokens/s of drafting and plain cycles, and skips 4, 8, 16, then 32 cycles. Under streaming a rejected verify costs more than resident, so the two are compared on the harness, not by reading.

## Goals / Non-Goals

**Goals:**
- Memory that is honest with the drafter loaded.
- A verify cycle's misses read no slower than one decode token's, per expert.
- Defaults chosen on the owner's content.

**Non-Goals:**
- A new drafter architecture. A Markov or other head beyond #1073's is not part of this.
- Server behavior (`340`).
- Changing the `82GB` measurement configuration.

## Decisions

### D1. Order by measured share
The steps run in the order of what `320` left on the table:
- the miss share of a verify cycle → S2;
- prose under the rule → S3 first;
- memory pressure → S5.

S1 always runs: it fixes a budget that over-commits.

### D2. S1 is judged on memory, not speed
- **Rule.** A budget that ignores the drafter can push static weights and the file cache out. The step's check is `310`'s timeline under the automatic budget: zero swapouts and at least 18 GiB available.
- **Measurement.** The harness A/B then runs under the explicit `82GB` flag, which this step leaves unchanged: bitwise, nothing below zero.

### D3. S5 only on evidence
A smaller drafter costs acceptance, because the drafter's errors become rejected rows. It is built only if both hold:
- the replay of `310` D5 shows that the slots the drafter takes cost more decode than the measured acceptance gap between MXFP4 and a Q2 drafter would give back;
- the owner agrees to publish the file.

## Risks / Trade-offs

- **[S2 adds reader contention with no gain]** → The step is kept only if the miss time of a cycle falls, measured with `--cache-stats`, and by the keep rule.
- **[S4 overfits the two harness texts]** → The defaults are checked once on the chat and tool kinds of `310`, and a cap that loses there is not chosen.
