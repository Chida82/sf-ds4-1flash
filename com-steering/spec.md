# spec.md — steering method and vector geometry

The stable part: what a steering direction *is* on this model, where it folds,
and how two directions compose. The moving part — what we are currently testing
— is [`investigation.md`](investigation.md). This file is the material; the
machinery (file format, opt-in, validation) is the engine law in
[`openspec/specs/directional-steering/spec.md`](../openspec/specs/directional-steering/spec.md),
and the runtime options are [`dir-steering/README.md`](../dir-steering/README.md).

## The fold site

One live site on V4.1: `v41_attn_input_weighted_fold_post_engram`, revision 2 —
the weighted HC attention-input fold, applied **after Engram and before the
norm**. A nonzero `--dir-steering-ffn` or `--dir-steering-attn` is refused on
this model; the residual fold is the only place a direction acts.

## A direction

A direction is a `40 × 5120` float32 matrix: one unit row per layer (row 0 is
all-zero — layer 0 is never steered), each other row either unit-norm (within
`1e-2`) or all-zero. It is applied per layer at the fold site, scaled by its
**residual** (the profile slot's `scale`). Raw
direction files are not shipped: a profile embeds its matrices, and the
provenance of each embedded direction is recorded in [`README.md`](README.md),
"Directions (provenance)".

## Two slots, and how they compose

A session can remove up to two directions at the same site (a profile's
slot 1 and slot 2).
Geometry decides what the pair does:

- **Orthogonal** directions compose as an exact rank-2 removal — a clean 2D
  subspace taken out at once.
- **Non-orthogonal** directions apply as two sequential rank-1 operations.

The engine prints the median `|cos|` between the two over the 39 non-zero layers
at open; the shipped pair sits at `0.105` (near-orthogonal). Each slot carries
its own scale and a phase gate.

## Phase gates

Each slot is gated to `both`, `think`, or `answer`. The right intervention
differs by reasoning phase (see `kpi.md`): a direction that helps the reasoning
trace can hurt the answer. Gate per slot, measure both phases, never assume one
transfers.

## Vector families

Named for where they came from, not for a model. How each was derived is in
[`README.md`](README.md), "Directions (provenance)".

| Family | What it is |
|---|---|
| `mrfk-q0` / `mrfk-q1` | the two rows of a global rank-2 refusal subspace (`mrfakename` 1017-abliterated); q0 is the dominant axis, q1 the second |
| `msuiche-1017` | a converted control vector, 1017-native |
| `dwarfstar-wo` | a weight-diff ("without-refusal") direction from the DwarfStar edit |
| `q0dwarf-equi` | the bisector of `mrfk-q0` and `dwarfstar-wo` (equiangular), per layer |
| `q0dwarf-interleave` | the same two inputs, alternating by layer instead of bisected |

**One fusion is never *the* fusion.** `equi` is a 50/50 bisector; every
composition idea must keep a variant that restarts from the two original
directions, not only from an already-fused one. (`fused`, in the search that
preceded the `1017` vectors, was the same 50/50 bisector of two older
directions, abliteration and msuiche: `unit(a+m)`.)
