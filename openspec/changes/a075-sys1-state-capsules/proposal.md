# Proposal

**Level: senior.** No engine edit, but it composes session state the model
never computed. It needs someone who can judge an approximation.

## Why

`830` reuses a state only as a **prefix**. Many real states are
recombinations of stable segments: a policy, a tool list, a user profile, a
retrieved document, a schema. Change one segment in the middle and
everything after it is prefilled again.

This model makes a different reuse conceivable. A token more than 128
positions back exists for the rest of the model only as compressed rows at
four layers (2, 8, 14: one row per two tokens; 20: one per token) plus their
index keys: 6400 bytes per token in the snapshot, stored at an index derived
from the position, with the position rotation already applied. A snapshot is
loaded with size checks only. So a segment's rows can be copied from one
snapshot into another at the same positions.

The result is an **approximation**: a spliced segment was encoded without
seeing its real neighbours. The literature on dense models reports a loss
for this on multi-document reasoning (CacheBlend, APE) and tolerance on
classification-like readouts, which is what a decision is. Two facts specific
to this model are in its favour: layers 0-1 see only 128 tokens, so the
layer-2 rows (serving layers 2-7) are identical to the joint encoding beyond
254 tokens; only the rows of layers 8, 14 and 20 differ.

Honest scope: prefix-extension callers gain nothing over `830`. The gain is
for recombined long segments and for mid-edits of states above 5K tokens,
and it is 1.2-3× there, not an order of magnitude.

## What Changes

- An experiment, then (only if it passes) a store of capsules in the server.
- Stage 1: a model-backed test that splices one segment's rows into a
  filler-encoded state and compares the decision with the joint encoding.
- Stage 2: a fixed-slot layout so capsules are reusable across compositions.

## Non-goals

- No change to chat, to the disk KV store, or to `830`. A spliced payload
  must never enter the chat's stores.
- No re-indexing of rows to other positions (the rotation is baked in and
  quantized).

## Impact

- New `sysone-bench/sf_splice.c` (public API), `Makefile` rule, record.
- Stage 2: server-side capsule store beside `830`'s cache.
