# Proposal

**Level: senior.** Edits the indexer selection on the token path of `ds4.c`.
Research probe; start only if `a065` passes.

## Why

`a065` reports which rows a decision's indexer scored highest. That is a
correlate, not a cause. The cheap causal test on a dense model is an
ablation: remove the span and re-run, a 6-7 s sweep per span here. This model
offers a cheaper one: decoder layers reach far context **only** through the
selected rows, and a candidate filter already exists on the token path
(layers after 20 use it with a block mask). Masking a span out of the
candidates at the readout suffix costs only the suffix again (0.3-2 s), from
the same snapshot.

What it can and cannot show, stated before anyone runs it:

- A drop in the chosen option's log-probability when the gold span is masked
  and none for a random span of equal length means the decision **read that
  span directly**.
- No drop proves nothing: later rows of the state may already have absorbed
  the fact, and the last 128 tokens are read raw, not through the selection.

So its use is narrow: a necessity signal for `a065`'s evidence, a cheap label
source to fit an evidence readout, and a recorded fact about how far this
model carries information forward in later rows.

## What Changes

- A test-only knockout mask applied to the indexer's candidates at layers 2,
  8, 14, 20 (and through the layer-20 block mask for 24-36), token path only.
- A gold-versus-random experiment on `a065`'s planted-fact items.

## Non-goals

- No request feature. No "focus" (a textual pointer over a list state does
  it with no engine code). No "pin" (send the section as the state).
- No masks above 16384 rows, under TP, on a sweep, or on a session that is
  then saved.

## Impact

- `ds4.c`: `ds41_attention_pick` / `ds41_attention_candidates` and one field;
  a permanent conflict site if kept, so it is reverted unless the owner keeps
  it.
