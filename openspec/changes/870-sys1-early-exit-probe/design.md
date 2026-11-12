# Design

Depends on `810`, `820`, and on the outcome of `865`. **This change edits
`ds4.c`.** The edits are listed one by one; anything beyond them (another
function, any kernel, `ds4_metal.m`) is out of scope: stop and ask the owner.

## The four edits (`ds4.c`, `ds41_graph_step`)

Before the layer loop (`for (uint32_t il = 0; ok && il < DS4_N_LAYER; il++)`):

```c
/* sf: 870 probe: read the logits after layer L-1 instead of the last layer. */
uint32_t exit_layer = DS4_N_LAYER;
{
    const char *v = getenv("DS4_V41_EXIT_LAYER");
    const long n = v ? strtol(v, NULL, 10) : 0;
    if (n >= 1 && n < (long)DS4_N_LAYER) exit_layer = (uint32_t)n;
}
```

Then, inside that function and nowhere else:

1. the loop bound `il < DS4_N_LAYER` → `il < exit_layer`;
2. the drain condition `il + 1u == DS4_N_LAYER` → `il + 1u == exit_layer`;
3. the re-begin condition `il + 1u < DS4_N_LAYER` → `il + 1u < exit_layer`;
4. **the fold hand-over.** Directly after the existing block

   ```c
   if (ok) {
       ok = ds41_graph_layer(g, m, l, il, token);
   }
   ```

   add

   ```c
   /* sf: 870 the head folds the streams with g->pre, which only the last
    * layer's carry fills; an early exit must hand over its own split. */
   if (ok && exit_layer < DS4_N_LAYER && il + 1u == exit_layer)
       ok = ds4_gpu_tensor_copy(g->pre, 0, g->ffn_split, 0, DS4_N_HC * sizeof(float)) != 0;
   ```

Why edit 4 is required (read this before touching anything): every step
starts by writing `{1, 0, 0, 0}` into `g->pre`. `ds41_graph_logits` folds the
four residual streams with `g->pre`. The only place that copies a block's
stream weights (`g->ffn_split`) into `g->pre` is the last line of
`ds41_graph_after_moe`, and it runs only when its `carry` argument is true,
which `ds41_graph_layer` sets as `il + 1u == DS4_N_LAYER`. With a lower loop
bound that copy never runs, and the head would read stream 0 alone: every
figure below layer 40 would be wrong. Edit 4 makes the same copy at the exit
layer. It must sit **before** the drain, while the command batch is still
open: `ds4_gpu_tensor_copy` is a queued blit and returns 0 with no open batch.

Do not edit `ds41_graph_layer` or `ds41_graph_after_moe`: `ds41_graph_layer`
has a second caller in the prefill path that must keep `DS4_N_LAYER`.

`ds4_env.def`: `DS4_ENV(DS4_V41_EXIT_LAYER, probe, unset, "V4.1 decode step: stop after layer N-1 and read the logits there (1-39); token-major path only")`.
`make test` must pass; `env-check` is its first step and fails on an
unregistered name.

Two layers are special: the Engram rows of layers 1 and 14 are added before
that layer's attention. An exit at L = 14 stops before layer 14 runs, so it
does not contain that add. This is correct for an exit; just do not compare
it with a hidden row captured *inside* layer 14 by another tool.

## Restrictions while probing

- Always set `DS4_METAL_DISABLE_V41_LAYER_PREFILL=1` with the probe, so every
  prefill row goes through `ds41_graph_step`. Without it a sweep runs all 40
  layers on the state and the step then reads stale upper-layer state.
- States under 250 tokens (8 s of prefill at 31 ms per token).
- Single box, SSD streaming, no TP, no `--boost`, no steering profile.
- No KV disk cache and `--sysone-state-cache 0`: a snapshot taken at one L
  must never be restored at another.
- One server process per L. Never change the variable inside a process.

## Bitwise guard

With the variable unset: `make test-deepseek41-metal`, `make test-sysone`
(the `800` determinism and isolation checks), and
`speed-bench/ab_bench.py --kinds decode --bitwise` against the commit before
the edit.

## Stage 0a: does a truncated token cost L/40? (run first, needs no `800`)

Expected: about 5 ms + 0.64 ms × L per token, so 12.7, 17.8, 22.9 ms at
L = 12, 20, 28 against 30.6 ms at 40.

For L in 40, 28, 20, 12: start
`DS4_V41_EXIT_LAYER=L DS4_METAL_DISABLE_V41_LAYER_PREFILL=1 ./sf-ds4-1flash-server --ssd-streaming --ctx 8192 --ssd-streaming-cache-experts 82GB`
(L = 40: only the second variable). Then, in that one process:

1. one warm-up chat completion (any 250-token prompt, `max_tokens` 1);
2. five **different** prompts of about 250 tokens (take five disjoint
   250-token slices of `speed-bench/promessi_sposi.txt`), each as a chat
   completion with `max_tokens` 1 and `reasoning_effort` `none`;
3. for each, ms per prefilled token = the server's logged prefill time ÷ its
   prompt tokens; keep the median of the five.

Never measure with one CLI process per run: a fresh process's first prefill
carries about 4.5 s of unrelated cost and would hide the effect. The model
answers nonsense at L < 40; only the timing is read.

| Result | Next |
|---|---|
| t(20)/t(40) ≤ 0.65 and t(28)/t(40) ≤ 0.80 | Stage 0b |
| t(20)/t(40) > 0.75 | **Stop.** Fewer layers do not pay. Record the four medians, recommend stop, revert the edits |
| in between | Stage 0b, and state the measured ratio wherever a saving is quoted |

## Stage 0b: the raw readout per layer

Items: `fixtures-it.jsonl` (60) plus the first 240 `typed-decisions` test
items whose state is under 250 tokens. For L in 40, 36, 32, 28, 24, 20, 16,
12, 8: one server process (flags as in 0a plus `--sysone-state-cache 0`), then
`run.py --mode sysone --sf '{"debug":true}' --out results-L<L>.jsonl`.
About 2.8 h of model time in all. **Keep every results file**: stage 1 and the
contrast analysis read them.

Record per L in `sysone-bench/record.md`: accuracy with interval; agreement
(share of items whose top equals the L = 40 top); mean legal mass; ms per
suffix token. Intervals are bootstrapped by **state**, not by item: the set
has about five decisions per state and they are correlated.

| Result | Next |
|---|---|
| Some L ≤ 32 has agreement ≥ 95% and mean legal mass ≥ 0.5 | Skip stage 1. Recommend the follow-up with that L |
| Otherwise | Stage 1 at the two highest L ≤ 32 that passed the 0a ratio |

## Stage 1: fitted readouts

### Capture edit (`ds4.c`, `ds41_graph_logits`)

When `DS4_V41_LENS_CAPTURE` names a file: after the function has read the
logits back and before it returns, read `g->norm` (5120 `float32`, shared
CPU/GPU storage, valid there because the function has just drained its
batch) with `ds4_gpu_tensor_read` and append one record: `uint32 pos`
(`g->pos`), then 5120 `float32`. Register the variable in `ds4_env.def`
(probe). If `ds4_gpu_tensor_bytes(g->norm)` is smaller than 5120 × 4, stop and
ask.

**Two records are written per request**, because a decision runs two syncs
(the state prefix, then prefix + suffix) and each ends with a head call. The
readout row is the **last record of the request**: join by taking, for each
request in order, the record with the largest `pos`.

### Data

Per candidate L: one run with `DS4_V41_EXIT_LAYER=L` and the capture on
(rows `x_L`). Targets: the L = 40 results file of stage 0b (option logits
`z40` and the L = 40 top). One question per request, sequential.

Split **by state**: states whose id hash is even are fit, odd are held out.
Report per question type and pooled. `noul` and `choice` share the symbols A
and B; `score` uses digits.

### Translators (`sysone-bench/lens_fit.py`, standard library only)

1. **Bias and temperature** on the exit-layer option logits `z_L` (from the
   stage 0b files; needs no capture): `ẑ_k = (z_L,k − b_k)/T`, one bias per
   symbol, one T; cross-entropy to the layer-40 distribution, plain gradient
   descent.
2. **Answer-symbol centroids** on `x_L`: for each symbol s, the mean row
   `μ_s` over fit rows whose layer-40 top is s, and one shared per-dimension
   variance `σ²`; score `−Σ_d (x_d − μ_s,d)² / σ²_d`, softmax with one
   temperature fitted by **leave-one-out** on the fit rows (with 200 rows in
   5120 dimensions the fit rows separate perfectly, so a temperature fitted
   on them directly is meaningless). Closed form, no solver. A symbol with
   fewer than 8 fit rows is reported as "too few rows" and excluded; digits
   will often be in that case, and `--rotate` cannot help `score`.
3. **Ridge probe** per symbol: `ẑ_k = w_k·x_L + c_k`, gradient descent with
   early stopping on a 20% slice of the fit states, ridge weight chosen on
   that slice from 1e-2, 1e-1, 1, 10.

Report held-out agreement with the L = 40 top and KL to the L = 40
distribution, per translator and L. For the centroids also report a
**schema split**: fit on two `typed-decisions` workflows, test on the other
two; a centroid result that holds by state but drops more than 10 points by
schema has learned the schemas, not the symbols.

A fitted readout is bound to its layout and template version: one fitted at
the `800` suffix position says nothing about `840`'s pointer position.

### Gate after stage 1

Recommend the follow-up only if some L ≤ 32 reaches held-out agreement ≥ 95%
with a translator, by state **and** by schema. Otherwise recommend stop.

## Offline by-product: layer contrast

From the stage 0b files only, no model time. For each L and for β in
0, 0.25, 0.5, 0.75, 1: among options within 2.30 logits of the L = 40 top
(the plausibility set; others keep their L = 40 probability),
`score_k = z40,k − β·zL,k`. Fit β on even states, report accuracy and NLL on
odd states against β = 0. Record one table. Keep nothing in the server: a
gain would need layer-L logits at the readout in production, which costs a
second pass. Published results on multiple choice are flat, so expect none.

## Deliverable

`docs/system-one.md`, section "Early exit": the timing row, the per-L table,
the translator table if stage 1 ran, the contrast table, and one of:

- **Stop.** Revert the `ds4.c` and `ds4_env.def` edits in this same change.
- **Follow up.** Keep the probe and list what a session-level exit layer
  needs, without doing it: the same bound and hand-over in
  `ds41_graph_prefill_sweep`; a measured per-layer cost of a sweep (unknown
  today); snapshots and both caches keyed by L; the translator shipped as a
  file bound like the calibration; a fallback rate f, since a fallback after
  a truncated state must redo the state at full depth (expected time
  `T_L + f·T_40`, break-even f ≈ 0.45 at L = 20).

## What must not be done here

- Not touch the sweep functions, `ds41_graph_layer`, `ds41_graph_after_moe`,
  `ds4_metal.m`, or any kernel.
- Not move edit 4 after the drain.
- Not run the probe without `DS4_METAL_DISABLE_V41_LAYER_PREFILL=1`.
- Not bootstrap by item, and not loosen a gate. A failed gate is the result.
