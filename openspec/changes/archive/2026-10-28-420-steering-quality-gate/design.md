# Design

## Context

See proposal.md for motivation. Every tool exists: `make test`, `make test-deepseek41-decode-switch SWITCH=<env>` for the documented bitwise switches, `make test-deepseek41-steering-admission` and `make test-deepseek41-steering-routes` from `401`, the parity oracle from StarForge (`SF_CHILD_DIR` points it at a worktree), `speed-bench/ab_bench.py` with the record's "Adding a row" procedure. The default path gained, across the series, one environment lookup per layer per token (`ds41_steering_active`) and the admission predicate at engine open; everything else is behind a nonzero scale.

## Goals / Non-Goals

**Goals:** one dated evidence set for the unsteered path after the series; a single place where the steered results and their intervention identity are read together; a go/no-go answer.

**Non-Goals:** no fix and no tuning inside this change. A loss found here opens its own change (the first candidate is caching the disable-switch read once per engine). No steered efficacy measurement: that is `402`'s.

## Decisions

### D1. Numbered with margin, run last
`420` leaves `406` to `419` free for whatever the series still needs. It runs on the tree where the last steering change landed; if a later steering change lands after it ran, it runs again, and the earlier evidence stays dated.

### D2. The unsteered guards are the acceptance
Bits: the switches and state controls must be exact, as their own changes claim. Parity: ten token-identical prompts, no speed trip. A/B: logits bitwise and no throughput metric's pooled 95% interval wholly below zero, by the project's rule for a step that claims no speed. A result outside that is reported by kind and interval and stops the gate; it does not get fixed here.

### D3. Results are collected, not remeasured
The steered overhead (`401`, 5.4) and `402`'s KPIs are copied with their dates, commands and intervention identity (site and revision). A number measured under another revision is listed as history, not as a result.

## Risks / Trade-offs

- [The A/B needs the segment's start worktree] -> built once as the record describes; if the segment changed since `401`, the row says which start it is against.
- [Two hours of model time] -> one process at a time, the fixed 82GB cache only for the harness; the state controls stay at 16 GiB because they reopen the engine in one process.
