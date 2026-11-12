# Design

Depends on `800` (the oracle uses its branches), `820`.

## What a tile writes (everything that must be saved or restored)

From `ds41_state_spans` (the complete list of persistent state) and the tile
body:

| State | Written at | Scope |
|---|---|---|
| `window[il]`, the 128-row ring | every layer, slot `pos % 128` | per layer, 256 KiB |
| `compressed[owner]`, `index_cache[owner]` | **only at the owner's source layer** (2, 8, 14, 20), at rows derived from the position | **shared by all follower layers** of that owner: 3-7, 9-13, 15-19, 21-39 |
| `previous_kv/score[owner]` (odd-position pending pair) | source layers 2, 8, 14 | per owner |
| per-row residual, pre, ffn_split, selected ids, block mask | between layers | the carry buffers (`ds41_carry_copy`) |
| Engram history | hashed from tokens | per branch, from a copy of the state's history |

The second row is the trap, and the reason a naive fork is wrong: follower
layers read the owner's rows **up to the tile's own positions**. If branch 1,
2, 3 each overwrite the rows past the state's end P at layer 20, then at
layer 21 every branch but the last reads the last branch's rows. Under 512
compressed rows the attention reads all of them, so the contamination is
certain. Each branch's owner tail must therefore be stashed after the source
layer and restored before every follower layer.

## Algorithm

Input: P = current position (end of what the session holds), an optional
state tile of n_s ≤ 2048 rows, K branches with lengths len_b; all rows laid
out at global offsets in the token and carry buffers
(n_s + Σ len_b ≤ `carry_cap`). Engram ids: the state from the live history;
each branch from a copy of the history at P' = P + n_s.

```
for each layer il:
    deliver the layer's weights as the sweep does (expert read start/join/bind)
    if n_s: run the state tile exactly as the unforked partition would;
            store its rows through ds41_carry_copy (always, even if n_s <= 2048);
            call ds41_prefill_seed after it (the decode cache is seeded from the state, not from a branch)
    save window[il]; if il in {2, 8, 14}: save the pending pair of its owner
    for each branch b:
        restore window[il] (and the pending pair at source layers); g->pos = P'
        load b's rows from the carry
        if il is a follower layer with compression:
            copy b's stashed tail back into compressed[owner] and index_cache[owner],
            rows [P'/ratio, (P'+len_b)/ratio)
        run the unchanged tile body with start = P'
        if il is a source layer (2, 8, 14, 20):
            stash that tail (about 2.5 KiB per compressed row; about 110 KiB per 45-row branch at layer 20)
        store b's rows to the carry
    restore window[il] and the pending pair
at layer 39: for each branch, fold its last row's residual with its ffn_split,
             BF16, output_norm; one batched ds41_output_projection over the K rows
             (the block ds41_graph_step_batch already has); read back K logit rows
finish: g->pos = P', history = the state's, g->residual / g->pre = the state's last row;
        the session is valid at P' exactly as after a state-only sweep
```

Write it as a **new sibling function** that calls the same helpers as
`ds41_graph_prefill_sweep` (expert read start/join/bind,
`ds41_before_attention_batch`, `ds41_attention_project_batch`,
`ds41_attention_batch`, `ds41_moe_batch`, `ds41_carry_copy`,
`ds41_prefill_seed`). Do not edit the existing sweep: a sibling leaves no
textual sync-conflict site, and an upstream change to a helper then shows as
a compile error or a failing oracle.

A state longer than 2048 new rows is swept first by the unchanged function;
a branches-only fork follows (one more sweep).

## Entry point (`ds4.h`)

```c
/* Evaluate `state` (may be empty) after the session's current prefix, then
 * each branch from the end of the state, in one layer sweep. On return the
 * session is valid at the end of the state; logits[b] holds branch b's
 * last-row logits (n_vocab floats each). Single box, SSD streaming,
 * unsteered, text only. Returns 0 on success. */
int ds4_session_fork_eval(ds4_session *s, const ds4_tokens *state,
                          const ds4_tokens *branches, int n_branches,
                          float *logits, char *err, size_t errlen);
```

Refuse (error, nothing changed) under TP, steering on, image state, a branch
of 2048 rows or more, or a total above `carry_cap`.

## Oracles (all bitwise; no tolerance anywhere)

1. **Per branch:** for at least 3 branches of **different lengths** (one
   branch, or equal lengths, cannot expose the owner-tail bug) after a
   1500-token state: branch b's logits equal
   `[load the state snapshot; ds4_session_sync(state + branch b)]` run with
   `DS4_METAL_V41_WARM_APPEND_MIN=1`, which forces that append to run as a
   sweep. Tiles under 32 rows take a different expert-buffer path in the
   existing sweep: include a 20-row branch and a 60-row branch.
2. **Session after the fork:** equal to the session after a state-only sweep
   (`state_equal` in `tests/test_deepseek41_prefill.c`), and its snapshot
   bytes equal.
3. **Chat untouched:** the existing sweep function has no diff; parity oracle
   and `ab_bench.py --bitwise` on the chat kinds.

If oracle 1 cannot be met exactly, stop and report which layer first
differs (compare per-layer carries between the two paths); do not ship.

## Step 0, before any code

`DS4_METAL_GRAPH_PREFILL_PROFILE=1` on harness appends of +300 and +1900
rows: the per-layer wait for the expert read must still be positive in most
layers at 1900 rows and the totals within about 1 s. If the GPU is already
the bound at 1900 rows, extra branch rows cost GPU time directly and the
premise fails: record and stop.

## Use and acceptance

`sf_sysone` takes the fork path when the branches' rows total at least 200
(below that, token-major branches are cheaper: a fork on a cached state pays
the 6.3 s fixed cost again). Under `830` a state-cache hit followed by a
branches-only fork breaks even near 5 questions.

Kept when, at 10 questions of about 45 tokens on a fresh 1500-token state,
the request is at least 2× faster than `800`'s branch path, and the bench's
accuracy is within the schedule noise recorded by `820`. The calibration
binding gains the path (`"readout":"fork"`).

Known cost: each sweep leaves the decode expert cache partly cold, so the
next chat token after a fork is slower (0.11-0.22 s for the first token, as
after any sweep).
