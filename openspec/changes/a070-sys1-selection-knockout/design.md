# Design

Depends on `a065` (its items, its token-to-line map, a "go" verdict) and `830`.

## Mechanism

Two CPU-written mask tensors per session, one per compression ratio:
ratio 2 (layers 2-19) and ratio 1 (layers 20-39), each `(rows + 7)/8`
floats in the format `g->block_mask` uses (8 rows per block; read how
`ds41_attention_candidates` fills and consumes it before writing one).

1. In `ds41_attention_pick`, before `ds41_attention_candidates`, at index
   source layers, when a knockout is set: call
   `ds4_gpu_dsv41_candidate_filter` on `g->index_scores` with the mask of
   that layer's ratio (the same kernel the token path already calls for
   layers after 20).
2. At layer 20, copy the caller's ratio-1 mask into `g->block_mask` in place
   of the all-allowed fill, so layers 24-36 inherit it.
3. `attended` passed to `ds41_attention` must be the number of **unmasked**
   visible rows (computed on the host per ratio), capped at 512. If it is 0
   take the existing `n_comp == 0` route: the gather and attention kernels
   reject `attended == 0`.
4. Refuse the mask (error at set time) when: the context exceeds 16384 rows;
   fewer than 512 unmasked rows would remain and the context has more than
   512 rows; TP; the next sync would run as a sweep (256 tokens or more);
   and refuse snapshot or payload save while a mask is set (follow
   `ds41_steering_refuses_persistence`). Clear the field on every row copy of
   the graph.

The mask is set through a test hook (`DS4_TEST_HOOKS`), not through `ds4.h`.

Granularity is a block of 8 rows: a masked span covers whole blocks, 16
tokens at ratio 2 and 8 tokens at ratio 1. Round the span outward and report
the rounded length; the random control uses the same number of blocks.

## Oracles

- An all-allowed mask is bitwise equal to no mask.
- With a mask leaving fewer than 512 finite scores, both top-k variants (the
  merge ladder and the radix select) return only unmasked ids: a kernel test
  in `tests/test_deepseek41_metal.c`.
- Unset: chat output bitwise unchanged.

## Experiment

`state_first` layout only (in `schema_first` the questions sit before the
state and the picture is different). The 30 fact items of `a065`, restricted
to those the model answers correctly and whose fact line is more than 300
tokens before the readout.

Per item, from the state snapshot: (1) plain suffix; (2) suffix with the
fact line's blocks masked; (3) suffix with a random span of the same block
count masked, three different spans. Report the change in the log-odds of the
correct option, gold against the mean of the random spans, paired.

| Result | Meaning |
|---|---|
| gold drop exceeds random with a paired interval excluding 0 on a clear majority of items | the decision reads the span directly; keep the probe as a label source for an evidence readout; record the median drop |
| no difference | "facts are carried forward by later rows; a selection knockout says nothing here": write it in `docs/MODEL_KNOWLEDGE.md`, revert the edits |

About 30 × 5 suffixes: ten minutes.
