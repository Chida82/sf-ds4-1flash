# Design

Depends on `810`, `820`. Read `a055`'s design first: the fold fact it explains
is the basis of this one.

## The identity

Layer il > 0 begins with `ds41_hc_mix(g, m, l, false, g->ffn_split, il)`:
it folds `g->residual` (4 × 5120) with the split weights the previous block
left in `g->ffn_split`. `ds41_graph_logits` folds `g->residual` with `g->pre`,
then BF16, `output_norm`, and the head. So at the top of iteration L
(before `ds41_graph_before_attention`, hence before layer L's Engram add),
`g->pre := g->ffn_split` followed by `ds41_graph_logits` is exactly the
readout of a model stopped after layer L−1.

Non-disturbance, to be **proved by the bitwise test, not assumed**:
`g->x` and `g->norm` are rewritten by `ds41_hc_mix` before any read;
`g->pre` is not read again for il ≥ 1 until the last layer's carry rewrites
it; `g->logits` is rewritten by the final head call.

## Edits

**(a) Trigger.** `ds41_gpu_graph` gains `bool lens_row;`. In the V4.1 chunk
loop of `ds4_session_sync`, before the `ds41_graph_step(..., NULL)` call of a
token-major chunk (`count == 1`): set
`g->lens_row = lens_on && i + 1 == prompt->len;` and clear it after the call.
`lens_on` is `getenv("DS4_V41_LENS_FILE") != NULL`, read once per sync.
Any row copy of the graph (`row = *g` patterns in the sweep code) must clear
the field; grep for struct copies of `ds41_gpu_graph` and check each.

**(b) Probe.** In `ds41_graph_step`, at the top of the loop body, when
`g->lens_row && il >= 1 && !layer_resident && g->tp_world == 1`:

```c
if (!ds4_gpu_end_commands()) ok = false;                 /* drain: per-layer drain is an existing mode */
float split[DS4_N_HC];
ok = ok && ds4_gpu_tensor_read(g->ffn_split, 0, split, sizeof(split)) &&
     ds4_gpu_tensor_write(g->pre, 0, split, sizeof(split)) &&
     ds41_graph_logits(g, m, w, lens_scratch) &&         /* opens and closes its own batch */
     ds41_lens_record(g, il, lens_scratch);
ok = ok && ds4_gpu_begin_commands() != 0;
```

`lens_scratch` is a `DS4_N_VOCAB` float buffer allocated once per process.
The read/write of the split are CPU copies and are valid only **after** the
drain. For that token the loop must also drain after every layer: treat
`g->lens_row` like `!queue_layers` in the `drain` expression.

**(c) Record.** `ds41_lens_record` appends to `DS4_V41_LENS_FILE`:
`uint32 pos`, `uint32 layer`, `float32 lse` (log-sum-exp over the
vocabulary), then one `float32` per id listed in `DS4_V41_LENS_IDS`
(comma-separated token ids, at most 64, parsed once). The engine does not
know option ids; the bench passes the 36 symbol ids `sf_sysone_open` found
(print them with `tests/test_sysone --tokens`). Dumping whole logits would be
20 MB per decision.

Layer 40's row comes from the normal final head; the bench has it through
`sf.debug`.

`ds4_env.def`: both variables, category probe.

## Oracles

1. **Unset:** bitwise as before (`make test-deepseek41-metal`,
   `make test-sysone`, `ab_bench.py --kinds decode --bitwise`).
2. **Set:** the decision's final option logits bitwise equal to a run with
   the variables unset, on the 12 fixtures of `800` and on 20 bench items
   with swept states. This is the proof that the probe does not disturb the
   token. If one bit differs: find which tensor the probe clobbered; do not
   ship a tolerance.
3. **Cross-check with `a055`:** for L = 20 and 32 on 10 token-major items, the
   lens row equals `a055`'s truncated readout bitwise (same schedule). If they
   differ, the two are not the same quantity and one design is wrong: stop.

Cost: 39 heads at about 1.2 ms plus 39 drains and readbacks, 0.06-0.1 s per
decision, only with the probe on.

## Run and analysis (`sysone-bench/lens_curves.py`)

One server, production flags plus the two variables. The full `820` item
set, both schedules occurring naturally (short states token-major, long
states swept). About 40 minutes. Per layer: agreement with layer 40, legal
mass, accuracy, with state-level intervals. Per item: depth = lowest L from
which the top equals the final top and stays.

| Question | Rule |
|---|---|
| Is a raw early exit alive? | agreement ≥ 95% at some L ≤ 32, else "dead as a raw readout" (fitted readouts are `a055` stage 1) |
| Is depth a better difficulty signal than confidence? | AUROC of depth against "the System One answer differs from the `think` answer" must exceed that of `1 − confidence` with a paired interval excluding 0; else drop depth |
| Does layer contrast help? | `a055`'s contrast table, now for every L; same expectation (flat) |

## Follow-up, not in this change

A production depth or contrast signal needs, per layer, K dots of the folded
row with the head rows of the option tokens **and** the row's squared norm
(the logit is `head_row · gain · x / rms(x)`; a dot without the norm keeps
the argmax but not margins or cross-layer contrasts). That is a new
read-only kernel; the steering kernel modifies the row in place and takes
one direction per dispatch, so it cannot be reused.
