# Design

Depends on `810` (the decision endpoint) and `820` (bench conventions).
**This change edits `ds4.c`.** The edits are listed; anything else is out of
scope: stop and ask the owner.

## What is read

In `ds41_attention_select_published` (`ds4.c`), at an index layer, the call
`ds4_gpu_dsv41_indexer_score_one_tensor(g->index_scores, ...)` writes
`n_comp` `float32` scores into `g->index_scores`: for each compressed row,
`Σ_h w_h · max(q_h·k_row / 64, 0)` over 32 heads. `g->index_scores` is one
scratch tensor shared by all layers, so after a token-major step it holds
the scores of the **last** index layer, 36. Layers 20-39 use one row per
token, so at layer 36 **row r is token r** and `n_comp` is the number of
tokens in the context including the current one.

Above 16384 rows a different call fills the tensor in candidate order.
The probe skips such contexts.

## Stage 1 edits (`ds4.c`)

**(a)** A new static function directly above `ds41_graph_logits`, inside the
same preprocessor region (so `make cpu` still builds):

```c
/* sf: a065 probe (DS4_V41_INDEX_PROBE=<file>): after a token-major row, the
 * last index layer's score for every token of the context. */
static void ds41_index_probe_dump(const ds41_gpu_graph *g) {
    const char *path = getenv("DS4_V41_INDEX_PROBE");
    const uint32_t n = g->pos;
    if (!path || n < 2u || n > 16384u) return;
    float *v = xmalloc((size_t)n * sizeof(float));
    FILE *fp = fopen(path, "ab");
    if (fp && ds4_gpu_tensor_read(g->index_scores, 0, v, (uint64_t)n * sizeof(float))) {
        fwrite(&n, sizeof(n), 1, fp);
        fwrite(v, sizeof(float), n, fp);
    }
    if (fp) fclose(fp);
    free(v);
}
```

Before relying on `n = g->pos`: read the end of `ds41_graph_step` and confirm
that `g->pos` has been advanced past the token just evaluated when the
function returns. If it has not, the count is `g->pos + 1`. Write which one
you found in the PR text.

**(b)** In the V4.1 branch of `ds4_session_sync`, find the chunk loop that
contains `const bool layer_major = count > 1u;`. Declare
`bool last_row_token_major = false;` just before that loop, and directly
after the `if (!ok) { ... }` block of the loop add
`last_row_token_major = !layer_major;`.

**(c)** In the same function, in the block that starts
`if (pending_logits) {`, directly after the successful
`ds41_graph_logits(...)` call (after its failure `if` block), add
`if (last_row_token_major) ds41_index_probe_dump(g);`.

That head call has just drained the GPU and read the logits back, so the
scratch tensor is complete and a plain read is safe there. It is **not** safe
between layers; do not move the read.

`ds4_env.def`: `DS4_ENV(DS4_V41_INDEX_PROBE, probe, unset, "V4.1 sync: after a token-major last row, append the last index layer's per-token scores to this file")`.

A decision makes two syncs. The state sync of a state of 256 tokens or more
ends in a sweep (no record); the suffix sync is token-major (one record). A
short state gives two records. The evaluator takes, per request, the record
with the largest `n`.

Guard, variable unset: `make test`, `make test-deepseek41-metal`,
`make test-sysone`, `ab_bench.py --kinds decode --bitwise` against the
previous commit.

## Server addition (`sysone_job`, with `sf.debug`)

Add to the response's `sf` object:

- `state_token_start`: the index, in the state prefix tokens, of the first
  token of the state text (the count of tokens before step 5 of the `800`
  prefix);
- `token_bytes`: for each prefix token from that index on, the byte length of
  `ds4_token_text(e, token, &len)`.

The evaluator accumulates the lengths to map each token to a byte range of
the state text, then to a line. Unit test: for a fixed token list the sum of
`token_bytes` equals the UTF-8 length of the state text; if it does not (the
tokenizer normalises something), stop and report the first differing offset.

## Items (`sysone-bench/evidence_items.py`)

Deterministic (fixed seed). 60 items, Italian:

- Filler: lines of `speed-bench/promessi_sposi.txt`, each line cut to at most
  160 characters, shuffled; take enough lines for a state of about 3000
  tokens (about 9000 characters: estimate 3 characters per token; the server
  refuses nothing at this size with `--ctx 32768`).
- 30 items **with** a planted fact: one line from a list of 30 hand-written
  facts unrelated to the novel (a warehouse unlock code, a train platform, an
  invoice amount, a meeting room…), inserted at a random line index that is
  **not** among the last 25 lines (so it lies outside the 128-token raw
  window of the readout) and not among the first 5.
- 30 controls: the same states without the fact.
- Question: a `choice` among 4 values, one correct, for example
  "Qual è il codice di sblocco del magazzino?" with four codes.
- Each item also gets a **content-free twin**: the same state and options
  with the instructions replaced by "Scegli un'opzione." It gives the prior
  score of each line (recency and position), to subtract.

## Evaluation (`sysone-bench/evidence_eval.py`)

Server: `DS4_V41_INDEX_PROBE=<work>/index.bin ./sf-ds4-1flash-server --ssd-streaming --ctx 32768 --ssd-streaming-cache-experts 82GB --sysone-state-cache 0`.
Send each item, then its twin, sequentially, with `"sf":{"debug":true}`.
About 120 requests × (12 s state + 2 s suffix) ≈ 30 minutes.

Per item: line score = mean score of the line's tokens; rank the lines.
Report, raw and prior-subtracted (item minus twin, per token):

- recall@5 and mean reciprocal rank of the fact's line, on the 30 fact items;
- on the 30 controls: the share where the top line's score exceeds the fact
  items' median top score (a crude "nothing here" separation);
- accuracy of the letter readout on the fact items (if the model does not
  answer correctly, its evidence means little: report recall only over
  correctly answered items as well).

| Result (best of raw and prior-subtracted) | Next |
|---|---|
| recall@5 ≥ 70% | **Go**: write the follow-up list for `sf.evidence` (below) and ask the owner |
| recall@5 < 40% | Stage 2 once, at layer 20; if that is also under 70%, stop |
| in between | Stage 2 |

## Stage 2 (by the gate): all index layers

The readout token queues all its layers and drains once at the end, so a
mid-layer score must be **copied on the GPU inside the token's own command
stream**. In the layer loop of `ds41_graph_step`, directly after the
`ds41_graph_layer` block (and after `a055`'s hand-over statement if present),
when the probe is on and `ds41_index_source(il)`:

```c
ok = ds4_gpu_tensor_copy(capture, (uint64_t)slot * g->ctx * sizeof(float),
                         g->index_scores, 0, (uint64_t)n_comp * sizeof(float)) != 0;
```

with `slot` 0..7 in layer order, `n_comp = ratio ? (g->pos + 1u) / ratio : 0`
from `ds4_layer_compress_ratio(il)` (skip when 0), and `capture` a tensor of
`8 × ctx` floats. Rows map to tokens as: layers 2, 8, 14 → row r covers
tokens 2r and 2r+1; layers 20-36 → row r is token r.

The capture tensor's allocation is the one part this design does not spell
out, because it must follow how the graph's own tensors are created
(`ds41_graph_alloc`, the `X(...)` list near `index_scores`). Add it to that
list as `X(index_capture, 8u * g->ctx)` only if the probe variable is set at
allocation time; if the list cannot be made conditional, **stop and show the
owner the diff before running anything**: an unconditional entry costs 1 MiB
at a 32K context and 32 MiB at 1M for every session.

Stage 2 dumps the eight slots after the final drain, from the same place as
stage 1. The evaluator reports the stage 1 metrics per index layer, plus the
max over layers.

## Deliverable

`docs/system-one.md`, section "Evidence": the tables and one of:

- **Stop.** Revert the `ds4.c`, `ds4_env.def` edits; keep the server's
  `token_bytes` (it is useful for debugging) only if the owner says so.
- **Follow up**, as a list, not as code: a per-session capture switched by a
  flag instead of an environment variable; `sf.evidence` returning the top
  spans per answer with byte ranges; the content-free prior cached with the
  state snapshot (one extra suffix per state); the sentence the docs must
  carry — "these are the rows this decision could read beyond its last 128
  tokens, not a proof of what decided it".

## What must not be done here

- Not read `g->index_scores` anywhere but after the head call of step (c).
- Not capture on the sweep path, and not above 16384 tokens.
- Not build `sf.evidence`, `locate` or a rerank endpoint.
- Not treat a high recall on wrongly answered items as success.
