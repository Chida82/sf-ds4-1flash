# Design

## Context

See proposal.md for the motivation.

The `145` probe on `50ff39c` measured, for a prediction made from the layer before (lead about 1 ms):

| Policy | Misses caught per token | Wasted reads per token |
|---|---|---|
| Top 6, 1 per layer | 0.95 | 7.3 |
| Top 12, 2 per layer | 1.82 | 36.5 |
| Top 16, all uncached | 2.32 | 84.8 |

There were 3.91 misses per token. A caught miss is worth about 0.8 ms, the read plus its 0.40 ms prepare.

`145` measured the minimal variant (layers 20-39, one read per layer, through the existing pending-load slot) and dropped it:
- decode 2048 -2.1%, decode 8192 -1.7%, both CIs below zero;
- it caught 0.48 misses per token, as predicted;
- the guess cost 85 us per layer on the CPU (7.9 MB of F32 router weights read each time), and there were 1.9 wasted reads per token.

So this change must first make the guess nearly free. Candidates:
- a small reduced-precision copy of the router weights;
- the guess on the GPU, inside the previous layer's command buffer, if its kernel time stays under a few microseconds;
- guessing only where the probe's precision is highest.

The miss reads it hides are worth at most 2-3 ms per token.

## Goals / Non-Goals

**Goals:** hide decode miss time with a guess cheap enough to pay for itself, without evicting useful experts.

**Non-Goals:**
- Changing which experts the router selects.
- Changing the cache budget or its victim policy.
- Prefill.

## Decisions

### D1. Gate

Measure the cost of the cheapest guess first; stop if it exceeds a third of the hideable time. Then rerun the `145` probe on the current tree. Compute the full variant's ceiling, net of wasted reads at the drive's measured rate, against the current state. Stop with a Rejected-ideas row if the gain cannot clear the harness resolution.

### D2. Staging and reader pool

A fixed set of staging slots (two layers by three experts at most) lives outside the cache budget, so a wrong guess evicts nothing. Prefetch reads run on their own small pool: a demand miss never queues behind a speculative read. On selection, a staged expert moves into the cache like a loaded miss, taking the victim at that point. An unselected one is released.

### D3. Policy

The window, cap and score margin come from the D1 probe on the current tree. Experts just predicted are protected from eviction until their layer is bound.

### D4. Replica and learned predictor

Each is a separate step, measured only if D2/D3 leave wasted reads or misses worth it:
- reading prefetches from the `140` replica needs the wider validation of `145` D6;
- a learned predictor would run on the GPU, in the command buffer of the layer before.

### D5. Measurement

Steps are judged with the harness against the previous kept state, `decode,append` plus guards, `--bitwise`, with cache statistics. The final A/B runs against the segment start, followed by parity.

## Risks / Trade-offs

- [Wasted reads compete with demand misses on the drive] -> separate pool, bounded cap, measured.
- [Staging memory is taken from the system] -> fixed and small, counted in memory admission.
- [Complexity in the cache code] -> kept only under the project rule, with fixtures for settlement and failure.
