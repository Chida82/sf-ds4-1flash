# Design

Line numbers are those of `main` at `1aff8d2`. They drift: find every site by
its identifier (`grep -n`), never by number.

## Context

See `proposal.md` for the motivation and `780`'s `design.md` for how a short
sweep runs today. What matters here:

**The layer loop** (`ds41_graph_prefill_sweep`, `ds4.c` about 25444). Before
the loop, the read of layer 0 starts. Then, for each layer `il`:

```c
ds41_prefill_expert_slot *slot = &expert_slots[il & 1u];
ok = ds41_prefill_expert_read_join(slot) &&
    ds4_gpu_stream_prefill_bind_layer(&slot->table,
        slot->tensor[0], slot->tensor[1], slot->tensor[2]);
if (ok && il + 1u < DS4_N_LAYER)
    ok = ds41_prefill_expert_read_start(&expert_slots[(il + 1u) & 1u],
                                        m, &w->layer[il + 1u], il + 1u);
```

then one command batch: before-attention, attention, after-attention (which
produces `batch.norm`), `ds41_moe_batch`, the adds and the HC expand,
`ds4_gpu_end_commands()`, and `ds41_prefill_seed`.

**`ds41_moe_batch`** (about 24523) is one `&&` chain: router logits
(`ds41_matmul_batch(b->route_logits, ...)`), selection (`ds41_route_batch`,
which writes `b->selected`), the shared expert, the routed experts
(`ds4_gpu_routed_moe_batch_tensor`, the only reader of the bound buffers),
the add, `ds41_sum_partial_batch`. It has a second caller (about 25877, the
TP/partial path) that must keep working unchanged.

**Delivery** (`ds41_prefill_expert_read_start`, about 25377):
`ds4_gpu_stream_prefill_copy_cached` (`ds4_metal.m` about 17473) loops over
all experts of the layer, queues a blit for every cached, not in-flight
entry and sets `ready[e] = 1`; the reader threads (`ds41_prefill_expert_read`,
about 25247) then read every expert with `!ready[e]`, adjacent ones merged,
`up` from the replica on some readers when one is configured.
`model_bytes`/`replica_bytes` are computed from the same `!ready[e]` test.

**Binding** (`ds4_gpu_stream_prefill_bind_layer`, `ds4_metal.m` about 11947)
refuses unless the GPU is drained (`g_batch_cb || [g_pending_cbs count] != 0`
returns 0).

**The kernels.** `kernel_mul_mm_id_map0` (`metal/moe.metal`) reads only the
ids and builds a work list of non-empty tiles; the matmul kernels take the
expert from the work item (`(expert - args.tp_expert_base)*args.nb02`). Two
paths exist and both must be tested: `kernel_mul_mm_id_mpp` for 32-511 rows
and the `_mpp_packed` kernels from 512 rows.

**What the router needs:** `batch.norm` and the static router weights, mapped
by `metal_graph_stream_map_decode_static_all`. Not the layer's expert buffers.
But the ids of layer `il` need the output of layer `il - 1`, so a selective
read of layer `il` cannot start while layer `il - 1` computes: selective
delivery gives up the read-ahead.

**Not usable:** the upstream selected-address path
(`use_iq2_batch_selected_addr`, off here because `ds41_moe_batch` passes
`force_resident = true`) runs different kernels (addr-table `mul_mv`), which
may round differently. It is only a pattern for "end the batch, read ids,
begin again".

## Goals / Non-Goals

**Goals:**
- One-tile sweeps up to a row limit deliver only selected experts.
- Bitwise identical output, proven with poisoned undelivered bytes.
- `0` at the limit restores today's flow exactly.

**Non-Goals:**
- Sweeps of several tiles (`wide`), the deferred-decoder sweeps, the mmap
  fallback, TP, resident mode. They keep today's code path untouched.
- Avoiding the RAM blit of cached selected experts (binding cache slabs
  directly needs address-table kernels: different kernels, not bitwise).
- Guessing the next layer's experts to keep some read-ahead. Dropped ideas
  of this family are in perf-record (`170`, `145`); do not add one here.
- Any change to the seed, the cache policy or the schedule.

## Decisions

### D1. When a sweep is selective
In `ds41_graph_prefill_sweep`, once, before the layer loop:

```c
const bool selective = explicit_experts && !wide &&
    total_count <= selective_max;   /* one tile: off == 0, count == total_count */
```

`selective_max` comes from `DS4_METAL_V41_SELECTIVE_SWEEP_MAX`, read **per
sweep** (not cached in a static: the model-backed test flips it between two
sessions of one process), clamped to 0-2047; default `DS41_SELECTIVE_SWEEP_MAX`,
a `#define` set by step 5. It applies to first prefills too, not only
appends: the rule is about rows.

Also not selective when the sweep has visual spans, unless task 2.4 proves
`batch.selected` holds every row's ids in that case.

### D2. Split `ds41_moe_batch`
Split the chain into two static functions, with `ds41_moe_batch` calling one
after the other so both existing callers behave exactly as before:

- `ds41_moe_route_batch(g, m, l, count)`: the router logits and
  `ds41_route_batch`.
- `ds41_moe_experts_batch(g, m, l, il, count, shared_owner)`: everything
  after, in the same order and with the same grouping of `&&`/`||`. Copy the
  expression; do not re-parenthesise it (AGENTS.md, the `ds41_moe_partial`
  fold that lost its parentheses). Check with a diff of the two halves
  against the original text.

### D3. The selective layer
For a selective sweep, the top-of-layer join/bind/read-ahead block is
skipped (and the pre-loop read of layer 0 is not started). Inside the tile,
replacing the single `ds41_moe_batch` call:

```
ds41_moe_route_batch(...)                  # router, same batch as attention
ds4_gpu_end_commands()                     # drain: ids are now readable
selected = ds4_gpu_tensor_contents(g->batch.selected)
wanted[e] = 1 for every id in selected     # count * DS4_N_EXPERT_USED ids
ds41_prefill_expert_read_start(slot, m, layer, il, wanted)
ds41_prefill_expert_read_join(slot)
[poison, if the test variable is set]
ds4_gpu_stream_prefill_bind_layer(...)
ds4_gpu_begin_commands()
ds41_moe_experts_batch(...)
```

and the rest of the layer is unchanged. An id out of range fails the sweep
the same way `ds41_prefill_seed` does (`return false`).

Why a drain is acceptable: `bind_layer` needs a drained GPU anyway, and the
stage profile (`DS4_METAL_V41_STAGE_PROFILE`) already ends and reopens the
batch between stages without changing the output.

Alternative considered: keep the whole-layer read-ahead and cancel what is
not selected. Rejected: by the time the ids exist the readers have already
read a layer's worth, which is the cost to avoid.

### D4. The mask
- `ds41_prefill_expert_read_start` gains `const uint8_t *wanted` (`NULL` =
  all experts, today's behaviour; the non-selective call sites pass `NULL`).
- `ds4_gpu_stream_prefill_copy_cached` gains the same parameter and skips
  experts with `wanted && !wanted[e]` before its cache test. Update the
  declaration in `ds4_gpu.h`, the definition in `ds4_metal.m` and its two
  calls in `tests/test_deepseek41_graph.c` (`grep -n` finds exactly: one
  call in `ds4.c`, one definition, one declaration, two test calls; a
  different count means the tree changed, re-read before editing).
- After `copy_cached` returns, in `read_start`: `for e: if (wanted &&
  !wanted[e]) ready[e] = 1;` so the readers and the `model_bytes` /
  `replica_bytes` sums skip them with no reader change. `ram_bytes` counts
  only what was blitted.
- A layer where every selected expert is cached starts readers with nothing
  to read; task 2.6 checks that this is handled.

### D5. Poison
With `DS4_METAL_V41_SELECTIVE_SWEEP_POISON=1` (category `test`), after the
join and before the bind, `memset(slot->dst[j] + e * per[j], 0xFF, per[j])`
for every `e` with `!wanted[e]` and `j` in gate/up/down. It costs a layer's
worth of memory writes, so it is only for the test. Without it the
undelivered slots hold bytes of layer `il - 2`, which a wrong kernel could
read without any visible failure in most runs; with it, a wrong read
changes the output for certain.

### D6. Profile
Under `DS4_METAL_GRAPH_PREFILL_PROFILE`, the existing per-layer line stays
and a selective layer adds `selected=%u route_drain=%.3f deliver=%.3f ms`
(distinct selected experts; time from the layer's `begin` to the end of the
router drain; time from `read_start` to the end of `bind`). Step 5 reads
these to see where a selective layer's time goes.

### D7. The default limit
Measured, not assumed. Probe (task 5.1): bench appends of 256, 384, 512,
768, 1024, 1536 and 2040 rows on a 5K context, `-n 256`, with the limit at
`0` and at `2047`, ABBA, two runs per mode, reading each append's prefill
time. The default is the largest probed size at which selective delivery
is at least 3% faster in both ABBA pairs; every smaller probed size must
also win, otherwise the default is the largest size below the first loss.
If 256 rows does not win by 3%, STOP: the change is closed and recorded as
rejected.

### D8. Steps and their judges
- S1: D1-D6 with the default limit at 1024 → judged on correctness only.
- S2: the measured default (D7) → harness A/B against `main`, kinds
  `append,short,decode,cold-2500`, guards `guard-decode`, `--bitwise`.
  The cache-state check may drop pairs because bytes read differ by more
  than 5%; if it does, rerun with `--cache-policy-change` and say so in the
  record. Hits and misses themselves should be equal; if they are not, find
  out why before accepting (D-risk 3).
- Kept when the pooled 95% interval of `append +300` lies above zero and no
  other headline's lies wholly below zero (under 800 runtime lines).
- Final review pass over `ds41_graph_prefill_sweep`, the two moe halves and
  `read_start`, then the parity oracle.

## Risks / Trade-offs

1. [The seed copies an expert that was not delivered into the decode cache:
   wrong weights for every later token] → task 2.1 proves by reading
   `ds41_prefill_seed` and `ds4_gpu_stream_expert_cache_seed_experts_gpu_copy`
   that only experts with `frequency > 0` are copied; the model-backed test
   decodes 64 tokens after an append, with poison. STOP if the seed can pick
   a zero-frequency expert.
2. [A kernel reads an unselected expert] → poison test on both kernel paths
   (300 rows: `mpp`; 512 and 1000 rows: `mpp_packed`), and tasks 2.2-2.3
   read the two kernels the map did not open
   (`ds4_gpu_encode_moe_packed_rhs`, the pair-swiglu variant).
3. [The cache ends in a different state] → not expected (the blit takes no
   hit and moves no recency; the seed input is unchanged). The harness
   prints both hit rates; a difference is investigated, not waved through.
4. [Losing the read-ahead makes long one-tile sweeps slower] → the limit,
   measured in D7.
5. [One more drain per layer] → about 40 extra batches per sweep; visible in
   `route_drain`. If `route_drain` exceeds 15 ms per layer at 300 rows,
   report before going on.
6. [A tensor created in the first half of the batch is used in the second]
   → task 2.5 reads `ds41_moe_batch`'s operands: all are `g->batch` storage
   (`DS41_PREFILL_STORAGE`), which persists across batches.
7. [`780` counted the cache one layer earlier than this change looks at it]
   → small; the harness is the judge.

## Migration Plan

`DS4_METAL_V41_SELECTIVE_SWEEP_MAX=0` restores whole-layer delivery, bitwise.
