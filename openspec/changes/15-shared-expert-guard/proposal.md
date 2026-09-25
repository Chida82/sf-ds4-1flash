# Proposal

## Why

The deep prune (`f927102`) folded the CUDA-only `shared_queued` flag of
`ds41_moe_partial` into `false`, and the parentheses of the guard went with it.
Upstream (`0aaea5a`) reads:

```c
if (shared_here && !shared_queued &&
    (!ds41_matmul(gate) || !ds41_matmul(up) || !swiglu || !bf16 || !ds41_matmul(down)))
    return false;
```

The child reads (`ds4.c` ~24087):

```c
if ((shared_here && !false && !ds41_matmul(gate)) || !ds41_matmul(up) || !swiglu || !bf16 || !ds41_matmul(down))
    return false;
```

On one box `shared_here` is always true, so the two are equivalent. On a TP
pair, the rank that does not own the layer's shared expert skips the gate
projection but still runs up, SwiGLU, the BF16 rounding and down on every
layer. They use a stale gate, and the result is then discarded
(`shared_owner && tp_rank == (il & 1)` adds it on the owner only). Output stays
right, but GPU work is wasted on every layer. The site also differs from
upstream in a way that says nothing, which costs a conflict at every sync.

This is not a performance change for this machine. It is a correctness fix to
our own prune, and it restores upstream's text.

## What Changes

- Restore upstream's grouping without the removed flag:
  `if (shared_here && (!gate || !up || !swiglu || !bf16 || !down)) return false;`.
- Audit of the other constant folds the prune left:
  - `grep '!false\|false &&\|&& false\|| true'` over the sources finds two more
    sites, `ds4.c` ~17161 (`fuse_attn_out_hc`) and ~17625
    (`fuse_shared_down_hc`);
  - both are plain `&&` chains, where `!false &&` changes nothing;
  - delete those two `!false &&` lines in the same commit. They are artefacts of
    our fold, and each site already differs from upstream.
- Record the lesson in the child's `AGENTS.md`, under the prune notes: a
  constant fold inside a mixed `&&`/`||` expression must keep the original
  grouping; check with a diff against upstream at the site.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: `ds41_moe_partial` (one expression), and two lines in the kept
  `metal_graph_*` layer-slice path.
- One paragraph in `AGENTS.md`.
- Gate:
  - `make test` (read the suite names, not the exit code);
  - `make test-deepseek41-metal`;
  - the parity oracle with `SF_PARITY_FLAGS=--ssd-streaming`.

  There is no speed measurement: the single-box path is unchanged by
  construction. The TP effect can only be seen on a Mac pair.
