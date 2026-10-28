# Design

## Context

- **Server sampling.** The server samples with the request's settings, falling back to the DeepSeek thinking defaults for omitted knobs. Inside tool-call syntax it decodes greedily (`greedy_tool_syntax` in `ds4_server.c`). Under streaming, the multi-session batch is excluded (`ds41_sessions_batch_supported`), so the server decodes one session at a time.
- **Exact sampling.** #1073's cycle has an `exact` branch (`exact = rng && temperature > 0`) that accepts a draft with the target probability and resamples on rejection. `320` leaves it unreachable by turning drafting off when sampling.
- **Upstream's boundary fix.** `fc80bd6` handles V4 Flash DSpark response and mode boundaries by keeping a verifier snapshot and replaying a bounded prefix.

## Goals / Non-Goals

**Goals:**
- Drafting helps the owner's single sampled request without changing what it samples.
- Tool-call syntax stays greedy, exactly as without the flag.

**Non-Goals:**
- Drafting inside a multi-request batch.
- Opportunistic sampling.
- TP drafting.

## Decisions

### D1. Exact sampling only
- **Why exact sampling.** It is the only sampled mode that keeps the distribution. That keeps `--dspark` a speed option, which is what the output rule asks.
- **What it costs.** Acceptance is lower than greedy, because a matching draft is accepted with probability p rather than always.
- **The rejected alternative.** Upstream's opportunistic mode gains more but changes what is sampled. Porting it would need an explicit owner exception and its own change.

### D2. The boundary is a rejection
The cycle gets the caller's boundary check before it commits.
- **The cut.** The first accepted token after which the server's mode would change ends the accepted prefix.
- **What follows.** The rows after it go through `ds41_draft_rollback` like rejected rows, and the next token is chosen under the new mode.
- **What it reuses.** The rollback that already exists, with no snapshots and no replay.
- **Why not `fc80bd6`.** It is the V4 Flash answer for a graph that cannot roll back inside a cycle. V4.1's graph can, so it is an `idea`, not a port.

### D3. Single request only
- **The rule.** Drafting runs while one decode is active. Under streaming, sessions already decode one at a time, so a second request waits at the cycle boundary, never inside a cycle.
- **Why.** Concurrency is a minor focus for the owner. Drafting across a batch would need per-session verify rows in one pass, which upstream does not do either.

### D4. Measurement
- **The bench.** `serve_concurrency_bench.py` with one client, plain against `--dspark`, on four request sets: code, chat, tool calls, and prose with the thinking defaults. Medians and pair CIs.
- **The distribution check.** A model-backed test, fixed prefix: 2000 next-token samples with and without the flag, compared by a chi-square test at 1%. It is its own target, `make test-dspark-distribution`, like `test-deepseek41-decode-switch`, because it takes minutes.

### D5. The draft-length rule under exact sampling
- **The problem.** If `330` S4 made the expected-cost rule the default, it prices drafts with the confidence head's estimates. Under exact sampling a draft is kept with the target's probability of it, which is at most what the greedy match rate suggests. The rule would then over-draft on sampled requests.
- **The fix, measured first.**
  - Log predicted `P_j` against the observed acceptance per position on the four request sets of D4.
  - If they disagree, the sampled path scales `P_j` by a running ratio, observed over predicted acceptance per position, kept per session.
  - If the gap is too wide for a ratio to fix, sampled decoding keeps the threshold rule.
  - DeepInfer prices sampled and greedy requests with the same head and adds only a per-step temperature, so no ready answer exists to copy.
- **Not affected.** The rule changes how many drafts are verified, never which one is accepted, so the distribution check (D4) is unchanged.
- **If `330` kept the threshold rule,** this decision does not apply.

## Risks / Trade-offs

- **[Exact acceptance is too low to pay on sampled chat]** → The back-off returns it to plain decode, and the README says which request kinds gain.
- **[The boundary check misses a mode change]** → A test sends a request that enters tool syntax inside a drafted block, and checks the greedy tool tokens against a server without the flag.
