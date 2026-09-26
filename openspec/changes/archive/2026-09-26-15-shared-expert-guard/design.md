# Design

## Context

See proposal.md for the bug and the fix. The facts the approach rests on,
checked on `main` at `3b6e768` against `upstream/main` (`0aaea5a`):

- **`ds41_moe_partial`** (`ds4.c` ~24087, upstream ~40773).
  - Upstream computes `shared_queued` inside `#if !defined(__APPLE__) &&
    !defined(DS4_ROCM_BUILD)`, through `ds4_gpu_dsv41_shared_start`, so on
    Metal it is always `false`.
  - The prune removed that block and replaced the flag by `false` in place.
    That broke the parenthesized group `shared_here && !shared_queued && (...)`
    into `(shared_here && !false && gate) || up || swiglu || bf16 || down`, all
    on one line.
  - Upstream's routed call also has a `#ifndef __APPLE__` TP branch
    (`ds4_gpu_routed_moe_batch_owned_tensor`), which is absent in the child.
    That is correct, and out of scope here.
- **What each rank adds.** With `shared_owner` (TP world 2, and
  `DS4_METAL_DISABLE_V41_TP_SHARED_OWNER` unset):
  - `ds41_moe_partial` adds `g->shared` only on the rank with
    `tp_rank == (il & 1)`;
  - `ds41_moe_finish` does not add it (`shared_owner || add(...)`).

  So the non-owner's shared result is never read, and the four wasted kernels
  change no output.
- **The other three fold sites** are all in the kept layer-slice path:
  - `fuse_attn_out_hc`, `!false &&` (upstream: `!cuda_tp_attn &&`);
  - `fuse_shared_down_hc`, `!false &&` (upstream: `!cuda_tp_shared &&`);
  - `split_commands`, `|| false` (upstream: `|| imatrix != NULL`).

  The pipeline split does not run for V4.1 yet, and it is kept by the owner's
  decision.
- **Tests.**
  - `make test` is model-less.
  - `make test-deepseek41-metal` runs `tests/test_deepseek41_metal`, GPU
    kernels only, with no GGUF. It is not part of `make test`.
  - No test reaches `ds41_moe_partial` with `tp_world == 2`. The TP path runs
    only across two Macs.
  - The parity oracle loads the model.

## Goals / Non-Goals

**Goals:**
- The guard evaluates exactly as upstream's does on Metal.
- The site's text is as close to upstream's as the removed CUDA block allows,
  so that a sync conflicts only where the child really differs.

**Non-Goals:**
- Any speed claim. The single-box path is unchanged by construction.
- Restoring the CUDA `shared_queued` block, or upstream's non-Apple routed
  branch.
- A TP measurement. It needs a Mac pair.

## Decisions

### D1. The guard keeps upstream's shape, minus the flag

Replace the child's one-line expression with upstream's lines, minus
`!shared_queued &&`:

```c
if (shared_here &&
    (!ds41_matmul(g->shared_gate, m, l->ffn_gate_shexp, g->norm, true) ||
    !ds41_matmul(g->shared_up, m, l->ffn_up_shexp, g->norm, true) ||
    !ds4_gpu_swiglu_tensor(g->shared_mid, g->shared_gate, g->shared_up,
                          DS4_N_FF_EXP, DS4_SWIGLU_CLAMP_EXP, 1.0f) ||
    !ds41_bf16(g->shared_mid, DS4_N_FF_EXP) ||
    !ds41_matmul(g->shared, m, l->ffn_down_shexp, g->shared_mid, true))) return false;
```

Keeping upstream's line breaks means a later sync lines up with this hunk.

- Alternative: keep the child's one-line style. Rejected: it is the text that
  hid the bug, and every sync would conflict across the whole expression.

### D2. A marker names the removed CUDA block

One line above the guard:
`/* sf-ablate(cuda): shared_queued and ds4_gpu_dsv41_shared_start are CUDA-only; on Metal the shared expert always runs here */`.

The prune cut a whole conditional block here without a marker, and rule 10
asks for one at every non-obvious cut. At a sync, rerere and the marker
together explain why upstream's block is gone.

- Alternative: no marker, as the prune left it. Rejected: a missing marker is
  how the grouping went wrong unnoticed.

### D3. The three other constants are deleted, not replaced

Delete the three lines `!false &&` and `!false &&` and the `|| false`
operand, without reintroducing upstream's `cuda_tp_*` or `imatrix` terms.
Those names are gone from the child: `cuda_tp_*` by the deep prune,
`imatrix` by the no-quantization cut in `28ff1c0`.

The `split_commands` expression then ends at `n_tokens > 2048;`. Each site
already conflicts at a sync because of the removed names, so this adds no
new conflict site.

### D4. Equivalence argument instead of a TP test

- **One box.** `shared_owner` is false, so `shared_here` is true.
  - The child's `(true && true && gate) || up || swiglu || bf16 || down`
    evaluates the same calls in the same order as `true && (gate || up ||
    swiglu || bf16 || down)`.
  - Both stop at the first failure and return false.
  - Encoded work and output are therefore identical, and parity must be
    token-identical.
- **TP pair.**
  - The owner rank runs the same five calls as before.
  - The non-owner now runs none of them, as upstream does.
  - Its `g->shared` is not read (see Context), so output is unchanged there
    too.
  - This is argued, not tested. The proposal already says the TP effect is
    visible only on a pair.
- **The three deleted constants** are identity elements of their chains.
  Deleting them cannot change the value.

### D5. The lesson goes in `AGENTS.md`

Add a short paragraph to the child's "Removing code (ablation)" section. When
a constant fold lands inside a mixed `&&`/`||` expression, the original
grouping must be kept. Check each fold site with a diff against upstream,
not by reading the child alone.

It names this case (`ds41_moe_partial`, fixed in `15-shared-expert-guard`)
as the example.

### D6. Git

- Branch `fix/15-shared-expert-guard` from `main`.
- When the owner asks, the change lands as one commit on `main`:
  `fix(v41): restore the shared-expert guard grouping lost in the deep prune`.
- The owner's earlier landing request was a squash merge, a push of `main`
  and deleting the branch. It is repeated only on a new request.

## Risks / Trade-offs

- **An unnoticed side effect in the expression.** Mitigation: D4, plus the
  parity oracle and `make test-deepseek41-metal` on the changed build.
- **The TP non-owner path is unverified here.** Mitigation: the argument in
  D4. The next time a Mac pair is available, TP parity on the pair covers it.
- **The parity oracle loads the 341 GiB GGUF in streaming** (a long run).
  Mitigation: the tasks ask the owner before starting it, as agreed.

## Migration Plan

None. Rollback reverts the one commit.
