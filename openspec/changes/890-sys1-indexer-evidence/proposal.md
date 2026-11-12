# Proposal

## Why

This model has something the small dense models behind Jev, Laya, JevK5,
Rizzo Flow and CLM do not: a **trained relevance score for every row of the
context**, computed on every token. At eight "index" layers (2, 8, 14, 20,
24, 28, 32, 36) the current position's query is compared by dot product with
a stored key for each compressed row, over 32 heads, and the 512 best rows
are the only far context the following layers can read. It is the model's own
contrastive lookup, and its scores are thrown away after use.

Read at the decision's readout position, those scores say *which parts of the
state this decision looked at*. None of the surveyed systems returns
evidence for an answer. Uses, in order of how much they need to be true:

1. **Evidence**: per answer, the state spans with the highest score. It makes
   a decision checkable, which matters most on the long states (20K tokens
   and more) that only this model can read.
2. **Locate**: a typed question whose answer is a span of the state.
3. **Rerank**: thousands of candidates in a cached state, a 20-token query,
   candidates ranked by score, only the best few sent to the exact readout.

All three rest on one unmeasured fact: that the scores at a readout position
point at the lines that matter. Published measurements of the same mechanism
in DeepSeek V3.2 put its precision near 60% against exact attention, and the
scores carry a recency term. So this change is a probe with a kill rule, and
it builds no feature.

## What Changes

- Stage 1: an environment-gated dump of the last index layer's scores (layer
  36, one score per token of the context) after a token-major row; about 20
  lines in `ds4.c`. A `sf.debug` addition in the server that returns the
  byte length of each state token, so scores map to lines.
- A planted-fact item set and `sysone-bench/evidence_eval.py`: does the fact's
  line rank in the top 5 of its state?
- Stage 2 (only if stage 1 is inconclusive at layer 36): the same dump for
  all eight index layers, by a queued copy inside the decode step.
- A recommendation: stop, or a follow-up change for `sf.evidence`.

## Non-goals

- No `sf.evidence`, no `locate`, no rerank endpoint.
- No change to what the model computes: the probe only copies numbers out.
  With the variable unset, output is bitwise unchanged.
- No sweep-path capture; contexts above 16384 tokens are skipped (above that,
  later index layers score a candidate list in another order).

## Impact

- `ds4.c`: one static function and two small hooks in the V4.1 branch of
  `ds4_session_sync`; `ds4_env.def`. Stage 2 adds a hook in
  `ds41_graph_step`, the function `870` also edits.
- `ds4_server.c`: `sf.debug` returns `state_token_start` and `token_bytes`.
- `sysone-bench/`: item generator, evaluator, record.
