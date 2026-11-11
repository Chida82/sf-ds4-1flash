# Design

Line numbers are those of `main` at `1aff8d2`. They drift: find every site by
its identifier (`grep -n`), never by number.

## Context

How a short sweep runs today (`ds4.c`):

- `ds41_prefill_count` (about 24701) gives one sweep for an append of
  256-2047 rows. `ds41_graph_prefill_sweep` (about 25444) runs it as **one
  tile per layer**: the tile loop runs once, with `off == 0` and
  `count == total_count`.
- The explicit buffers are two slots (`ds41_prefill_expert_slot`, about
  24996), used alternately: layer `il` uses `expert_slots[il & 1u]`. Each
  slot has `ready[DS4_MAX_EXPERT]`: `ready[e] == 1` means expert `e` was
  blitted from the decode cache (`ds4_gpu_stream_prefill_copy_cached`,
  `ds4_metal.m` about 17473); `0` means the reader threads read it from disk.
- Per layer: join the slot's read, bind it, **start the read of layer
  `il + 1`**, then compute layer `il` in one command batch, drain
  (`ds4_gpu_end_commands`, about 25718), then `ds41_prefill_seed` (call
  about 25722).
- `ds41_prefill_seed` (about 24647) already reads the selected ids on the
  CPU with no extra readback:
  `const int32_t *selected = ds4_gpu_tensor_contents(g->batch.selected);`
  The tensor holds `count * DS4_N_EXPERT_USED` int32 (6 ids per row).
- The per-layer profile line under `DS4_METAL_GRAPH_PREFILL_PROFILE` (about
  25522) already prints the GiB that came from RAM, the model and the replica.

So everything the count needs is on the CPU after the layer's drain: the ids
in `g->batch.selected`, and the cache state at delivery time in
`expert_slots[il & 1u].ready`. `ready[]` of layer `il` is still intact
there: that slot is rewritten only when the read of layer `il + 2` starts,
at the top of layer `il + 1`.

`prefill_seed_router_selected` is a field of the old `ds4_gpu_graph`; the
V4.1 sweep never touches it. Do not use it. `DS4_MOE_RECORD_SELECTED_IDS`
records the single-token MoE path; do not use it either.

## Goals / Non-Goals

**Goals:**
- Count, per layer of a short sweep, the distinct selected experts and the
  distinct selected experts the cache did not hold.
- Decide `790` on fixed numbers.

**Non-Goals:**
- Any change to what a sweep reads, to the schedule, or to the cache.
- Timing. These runs count; they are not performance runs and are never
  quoted as speed.
- Sweeps of several tiles (2048 rows or more with `wide`): the ids of earlier
  tiles are overwritten, and `790` does not target them.

## Decisions

### D1. Where the count happens
In `ds41_graph_prefill_sweep`, right **before** the `ds41_prefill_seed` call,
inside the same `off + count == total_count` condition, and only when all of
these hold:

- the probe variable is set (read once per sweep, next to the existing
  `profile` read at about 25453, the same way that line reads its variable);
- `explicit_experts` is true (without it `ready[]` does not exist);
- `off == 0` (single tile).

Before the seed, because the seed changes the cache; the count describes the
state the delivery saw. Alternative considered: counting inside
`ds41_prefill_seed`. Rejected: the seed does not see the slot.

### D2. The helper
One static function in `ds4.c`, next to `ds41_prefill_seed`, pure (no GPU
call, no globals), so a model-less test can call it:

```c
/* Distinct routed experts a sweep's rows selected, and how many of them the
 * decode cache did not hold when the layer was delivered. */
static bool ds41_prefill_selected_stats(const int32_t *selected, uint32_t rows,
                                        const uint8_t *ready,
                                        uint32_t *distinct,
                                        uint32_t *distinct_uncached,
                                        uint32_t *uncached);
```

- `seen[DS4_MAX_EXPERT]` bytes on the stack, zeroed.
- For each of `rows * DS4_N_EXPERT_USED` ids: return `false` if the id is
  negative or `>= DS4_N_EXPERT` (the seed does the same check); if not seen,
  mark it, `distinct++`, and `distinct_uncached++` when `!ready[id]`.
- `uncached` = number of `e < DS4_N_EXPERT` with `!ready[e]`.

The output line, exactly:

```
ds4: V4.1 prefill selected layer=%u rows=%u distinct=%u distinct_uncached=%u uncached=%u
```

A `false` return prints nothing and does not fail the sweep.

### D3. The variable
`ds4_env.def`, in sorted position:

```
DS4_ENV(DS4_METAL_V41_PREFILL_SELECTED_STATS, probe, unset, "Print, per layer of a single-tile V4.1 prefill sweep with explicit expert buffers, the distinct selected experts and how many the decode cache did not hold")
```

`make env-check` fails until the name is both read in the source and listed.

### D4. The runs
All with the harness's fixed bench arguments, the probe and the profile:

```sh
DS4_METAL_V41_PREFILL_SELECTED_STATS=1 DS4_METAL_GRAPH_PREFILL_PROFILE=1 \
./sf-ds4-1flash-bench --ssd-streaming --ssd-streaming-cache-experts 82GB \
  --ctx-alloc 32768 --prompt-file <FILE> --frontiers <LIST> -n 256 \
  --cache-stats --show-output 2> "$OUT/<run>.err" > "$OUT/<run>.out"
```

`-n 256` generates between frontiers, so each append finds the cache as a
chat turn leaves it: seeded by the previous sweep, then changed by decode.

| Run | `<FILE>` | `<LIST>` | What it stands for |
|---|---|---|---|
| R1 | `speed-bench/promessi_sposi.txt` | `5000,5256,5556,6068,7068` | appends of 256, 300, 512, 1000 on a 5K context |
| R2 | `speed-bench/promessi_sposi.txt` | `2048,2304,2604,3116,4116` | the same appends on a 2K context |
| R3 | `ds4_server.c` | `5000,5256,5556,6068,7068` | another domain (C source) |
| R4 | `$OUT/mixed.txt` | `5000,5256,5556,6068,7068` | a domain change near the appends |

`$OUT/mixed.txt` is `head -c 12000 speed-bench/promessi_sposi.txt` followed
by `ds4_server.c`: Italian prose, then C. `$OUT` is `mktemp -d`; nothing is
written into the repository.

R1 and R2 append more of the same novel, the friendliest case for the cache.
R3 and R4 exist because a real user turn may route less like what is cached.

One model process at a time. If a run exits non-zero right after another one
was stopped, wait 15 s for the instance lock and run it again.

### D5. The summary
Per run, one line per append size:

```sh
grep 'V4.1 prefill selected' "$OUT/<run>.err" | awk '
{ for (i = 1; i <= NF; i++) { split($i, kv, "="); v[kv[1]] = kv[2] }
  r = v["rows"]; n[r]++; d[r] += v["distinct"];
  du[r] += v["distinct_uncached"]; u[r] += v["uncached"] }
END { for (r in n)
  printf "rows=%s layers=%d distinct/layer=%.1f uncached/layer=%.1f distinct_uncached/layer=%.1f r_all=%.3f r_disk=%.3f\n",
    r, n[r], d[r]/n[r], u[r]/n[r], du[r]/n[r], d[r]/(n[r]*384), du[r]/u[r] }'
```

- `r_all` = distinct selected / 384: the share of a layer `790` would deliver.
- `r_disk` = distinct selected and uncached / uncached: the share of today's
  disk bytes `790` would still read.
- `layers` must be 40 for every append size (80 if two appends have the same
  row count, which the lists above avoid). Anything else: the run is not
  valid; find out why before using it.

### D6. Gate
Read the `rows=300` lines of the four runs.

- **Go** (start `790`): `r_disk <= 0.60` and `r_all <= 0.75` in R1 and R2,
  and `r_disk <= 0.75` in R3 and R4.
- **No-go**: `r_disk > 0.85` at `rows=256` in R1 or in R2. Add the Rejected
  ideas row and stop; `790` is closed without code.
- **Grey** (neither): write the table in the record, do not start `790`,
  report the table to the owner.

Why these numbers: route-first delivery (`790`) gives up reading the next
layer while the current one computes and adds one GPU drain per layer. With
`r_disk` above about 0.85 nothing is left after that loss. Below 0.60 the
disk bytes of a 300-row sweep fall from about 70 GiB to under 42 GiB, which
at the drive's 13.6-16.6 GB/s is 1.7-2 s of a 6.3 s sweep even before the
RAM blit shrinks by `r_all`.

## Risks / Trade-offs

- [The bench's appends continue one text; a real turn changes subject] → R3
  and R4, with a looser bound, and the grey zone goes to the owner.
- [`ready[]` is the cache state when the layer's read started, one layer
  before its ids exist; `790` would look at the cache one layer later, after
  the previous layer's seed] → the difference is at most the experts one
  seed moves; record it as a known approximation, do not correct for it.
- [The probe line is printed inside a timed sweep] → the probe is never set
  in a harness run; the spec's "quiet by default" scenario guards it.
- [A count is not a time] → `790` measures time itself as its first step;
  this change only removes the case where `790` could not win.
