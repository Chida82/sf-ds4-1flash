# Performance record

Where the performance work on this child started, and where it has got to.
Each row is one `speed-bench/ab_bench.py` run, pasted from the `record row:`
line of its summary. A cell reads `B median (gain)`: the candidate's absolute
median under SSD streaming with the fixed 75 GiB expert cache, and its gain
against the segment's start commit, measured in the same session; positive is
faster for every metric (tokens/s up, seconds down). The gain is the figure to
read; the absolute numbers depend on the page cache, the room and the
machine's power mode.

## Situation 0 (2026-09-27, `main` at `a60b8ee`)

Three readings taken before any measurement, on the M5 Max 128 GB with the
Q2 GGUF on the internal SSD, nothing else resident.

**Parity.** `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh
sf-ds4-1flash` with the loader's auto budget (76.62 GiB total, 69.50 GiB
dynamic, 7498 slots): `PARITY OK (10 prompts)`, token-identical on all ten.
The CLI's generation figure read 8.9-15.4 tokens/s on the child against
7.4-13.8 upstream: the child runs second and finds the page cache warm, so
its edge (up to +28%) is order, not code.

**Speed against upstream at the merge-base** (`tools/speed-compare.sh` with
`SF_SPEED_FLAGS="--ssd-streaming --ssd-streaming-cache-experts 82GB"`, the
child first, 180 s of cooldown, upstream `0aaea5a` second; informational):

| ctx | new tokens | prefill up | prefill child | steady decode up | steady decode child |
|---|---|---|---|---|---|
| 2048 | 2048 | 122.3 t/s | 137.4 (+12.3%) | 15.09 t/s | 17.74 (+17.6%) |
| 4096 | +2048 | 114.9 | 120.4 (+4.8%) | 17.38 | 17.95 (+3.3%) |
| 8192 | +4096 | 206.6 | 208.9 (+1.1%) | 17.50 | 17.80 (+1.7%) |
| 16384 | +8192 | 360.3 | 361.1 (+0.2%) | 16.92 | 17.40 (+2.8%) |
| 32768 | +16384 | 492.5 | 515.6 (+4.7%) | 17.01 | 16.80 (-1.2%) |

The child is never slower than upstream by more than 2%; the first frontier
of each process is the noisiest. The cache flag `82GB` gives, on this
machine, `74.88 GiB dynamic cache (8078 experts, 9.49 MiB each)`: inside the
harness's 74.5-75.5 GiB window, above the 7680-slot threshold that keeps
appends under 1024 tokens token-major. Sweep times read from the child's
rows: 14.9 s for 2048 rows, 17.0 s for a +2048 chunk, 19.6 s for 4096 rows,
22.7 s for 8192 rows, 31.8 s for +16384 (two 8192-row sweeps).

**The 6, 13.39 and 17 tokens/s figures.** Every figure below is the child
at `82GB` (74.88 GiB dynamic cache) and ctx 32768, greedy, `--nothink`;
"cold" adds `--ssd-streaming-cold` (no popularity preload; the OS page cache
stays warm across runs either way). The CLI's `generation` divides every
generated token, the first included, by the time from the end of prefill; the
bench's `gen_steady_tps` excludes the first token.

| Figure | Where it comes from | Prompt | Generated | Conditions |
|---|---|---|---|---|
| 5.4-6.0 t/s | CLI `prefill:` of a 20-token prompt (token-major, fresh process, the cache holds only the preload) | 20 | - | warm 5.38, 5.91; cold 5.75, 5.97 |
| 11.6-12.7 t/s | CLI `generation:` after a 20-token prompt | 20 | 128 / ~170 (EOS) | warm 11.60, 12.63; cold 12.07, 12.68 |
| 15.6-16.8 t/s | CLI `generation:` after a 2783-token prompt (a 2048-row sweep plus 735 token-major) | 2783 | 128 / ~280 (EOS) | warm 15.56, 16.70; cold 15.59, 16.75; prefill 47-49 t/s = 57-59 s |
| 16.8-18.0 t/s | bench `gen_steady_tps` at 2048-32768 of context, 128 tokens | 2048+ | 128 | speed-compare table above |
| 12.8-14.0 t/s | bench `gen_tps`, the same runs with the first token included | 2048+ | 128 | first token after a sweep 2.1-2.4 s |
| 12.62 -> 13.39 | upstream `077a257`, "warm M5 Max SSD decode" | ? | ? | a CLI-style figure: it sits between the 20-token and the 2783-token rows |
| about 6 t/s | `AGENTS.md` at bootstrap | ? | ? | not reproduced under any condition above; the nearest number is the CLI's prefill rate of a short prompt, printed first on the same line as `generation:` |

Two shapes matter more than the figures. The first decode token after a
layer sweep costs 1.4-2.4 s (`gen_first_ms` 2126-2436 ms in the sweep, 1404
ms after the +1500 chunk of `append`), against 58-81 ms after a token-major
tail: a sweep leaves the decode path with a cold first layer. And a
token-major tail runs at the decode rate: `append +300` prefilled at 17.4
tokens/s, so a 452-token tail costs 27 s of the 42.9 s time to first token at
2500, and a 904-token tail 53 s of the 70.9 s at 5000, while one more sweep
would cost 15-17 s. `60-prefill-sweeps` reads this.

**Baseline decomposition** (2026-09-27, one probe run per shape with
`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`, `_LAYER_STATS`,
`DS4_METAL_GPU_BUSY_PROFILE`, `DS4_METAL_V41_STAGE_PROFILE` and
`DS4_METAL_CB_TIMES`; walls from the harness's A/A runs where the probes
perturbed them). The expert-path times are the streaming timing summary's
per-frontier deltas divided by the frontier's tokens; the stage times are the
V4.1 stage profile's host-timed sums over the 40 layers; "outside stages" is
the chunk's wall minus that sum.

| Shape | Wall | Where the time goes |
|---|---|---|
| decode token at 8K (hit rate 0.932, 16 misses of 240 lookups) | 56 ms (17.7 t/s) | expert path 44 ms = 78%: `sync` 38.0 (the GPU finishing the layer up to the router before the selected ids are read back; not the loads, see Read path below), bind 4.3, readahead 1.8, buffer prepare 0.2; the rest 12 ms is attention, Engram rows and host work. GPU busy 62% of the frontier (sweep included) |
| decode token at 2K (hit rate 0.868, 32 misses) | 58 ms (17.3 t/s) | the same path with twice the misses; the probe run itself read 5.1 t/s because `DS4_METAL_CB_TIMES` waits on every command buffer, so its split is not reported: never combine that probe with a timing |
| token-major prefill tail (904 tokens of `cold-5000`, hit rate 0.948) | 58 ms per token | expert path 43 ms = 74%: sync 35.1, bind 4.3, buffer prepare 2.2, readahead 1.8. A tail runs at the decode rate |
| first tokens after a wide sweep (16 tokens of `cold-10000`) | first 2.2 s, then 87 ms | per-layer hit rate 0.33-0.54 (mean 0.51): a wide sweep leaves the decode cache half cold, and the first token pays sync 131 ms and buffer prepare 109 ms per layer sweep-equivalent. After a token-major tail the first token costs 60-85 ms |
| 2048-row sweep from empty | 14.9-17.9 s | stages 9.1-10.2 s: shared/routed FFN 4.0-4.8, attention core/index 2.1-2.2, attention projections 1.0-1.3, HC/Engram 1.1-1.2, attention output 0.4-0.5, norms 0.3; outside stages 6-8 s (layer page-in and prepare between layers). GPU busy 45% of the `cold-2500` frontier |
| 6144-row wide sweep (`decode`'s +6144) | 26.9 s | three 2048-row tiles of 11.8, 5.3 and 5.7 s of stages (the first tile carries the Engram and projection costs, the later ones about 5 s: routed FFN 2, attention core 2); outside stages 4 s |
| 8192-row wide sweep plus 1808 chunk (`cold-10000`) | 41.4 s | two 4096-row tiles of 6.1 and 5.0 s of stages, the decoder suffix's per-layer shrinking tiles about 4 s, the 1808 chunk 10.3 s (routed FFN 5.0, attention core 2.0, Engram 1.3); GPU busy 45% |

Per-layer hit rate at 8K: 0.897 (layer 39) to 0.957, the last layers lowest;
at 2K: 0.824 (layer 0) to 0.886, the first layers lowest. Reads are page
cache warm: a miss's `pread` averages 0.54-0.68 ms for 9.49 MiB.

What the start gates read (corrected by `40`'s Read path below): the 38 ms of
`sync` per decode token are GPU work, the domain of `70-decode-glue-fusions`
and of the per-layer readback round trip; the missing experts' reads and
buffer preparation are about 4 ms of a token, the most `40` and
`50-ssd-miss-overlap` can recover; `60-prefill-sweeps` the 6-8 s outside the
stages of a sweep, the tail policy (a 904-token tail costs 53 s against 20 s
for one more sweep) and the half-cold cache a wide sweep leaves behind.

**Routing trace.** `cold-5000` with 2000 generated tokens and
`DS4_MOE_RECORD_SELECTED_IDS`: 116160 routed calls = 2904 tokens (the 904
token-major plus the 2000 decoded) over 40 MoE layers, 696960 lookups,
11088 distinct (layer, expert) pairs against 8078 slots. Replayed from an
empty cache by `speed-bench/expert_cache_sim.py`: LRU 12869 misses, Belady
11088 (every distinct pair once: with foresight the working set fits), the
run itself 15386 (hit rate 0.978). The current policy misses 20% more than
LRU and 39% more than the optimum: 1.5 misses per token out of 5.3. A miss
costs about 1 ms of host time (pread 0.5, buffer preparation 0.5; `sync` does
not grow with misses, see Read path), so a perfect policy is worth about
1.5 ms of a 52 ms token, 3% of decode, and an LRU about 2%. Not opened as
a change by this one: it is a candidate (`45-expert-cache-policy`, small,
bitwise by construction) to weigh after `50-ssd-miss-overlap` has changed
what a miss costs.

## Read path (2026-09-29, `40-ssd-expert-reads` S0)

`main` at `5410123` plus #570's pool counters, bench runs with
`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1 --cache-stats`, same streaming
configuration as the harness. Decode figures are the difference between a
256-token and a 16-token run at the same frontier, so the prefill, its seed
misses and the first token drop out.

| Shape | Per token | Where the time goes |
|---|---|---|
| decode at 2K (240 tokens, 4.4 misses per token, hit rate 0.982) | 51.8 ms (19.3 t/s) | `sync` 38.9 ms; pread 2.1 ms (4.0 dispatches of 0.51 ms, 41 MiB); buffer preparation 2.0 ms; the rest about 9 ms of encoding and bind |
| decode at 8K (256 tokens with the first, 2.4 misses per token) | 48.9 ms (20.5 t/s steady) | `sync` about 39 ms once the first token's 2 s is taken out; pread 1.9 ms (4.2 dispatches of 0.46 ms) |
| token-major tail of `cold-5000` (904 tokens plus 16 decoded, 4.2 misses per token) | about 50 ms | `sync` 42.8 ms; pread 2.2 ms; buffer preparation 2.0 ms |

The pool runs at `qd_avg` 2.2-2.4 with 3.3 tasks per dispatch and
`workers_avg` 3.3, so the 9-thread limit never binds in decode; it moves
19-24 GB/s (`pool_gbps`) and 9-10 GB/s per task, page cache included.

After `40` (`main` at `b044217`: split 4, 18 threads, slab residency; same
method, `50-ssd-miss-overlap` S0):

| Shape | Per token | Where the time goes |
|---|---|---|
| decode at 2K (240 tokens, 4.4 misses per token) | 45.6 ms (21.9 t/s) | `sync` 36.3 ms; pread 2.2 ms (4.0 dispatches of 0.55 ms); buffer preparation 1.6 ms |
| decode at 8K (256 tokens with the first) | 47.1 ms (21.2 t/s steady) | `sync` 41.2 ms with the first token; pread 2.1 ms; buffer preparation 2.5 ms |
| token-major tail of `cold-5000` (4.2 misses per step) | about 45 ms | `sync` 38.5 ms; pread 2.3 ms; buffer preparation 1.9 ms |

The split raised the pool's `qd_avg` from 2.2 to 6.8 (12.8 tasks, 12.4
workers per dispatch) without shortening a dispatch (0.51 -> 0.55 ms): the
pool moves about 20 GB/s either way, the rate of copying from the page cache.
The token got shorter by the residency set, not by the reads. `50`'s S2 gate
(`0.46 x pread >= 2 x 1.5% of the token`): 1.03 ms against 1.37 ms, closed.

`sync` is the wait at the per-layer selected-id readback
(`ds4_gpu_routed_moe_one_tensor`: `end_commands` or the shared-event wait,
then `tensor_read` of the ids), timed before any load starts. It is the GPU
finishing the layer's queued work up to the router, and it does not grow
with misses: 38.9 ms at 4.4 misses per token, about 39 ms at 2.4. Situation
0 had called it the wait for the missing experts' loads; the loads are the
pread and buffer preparation after it, about 4 ms a token (8%). That bounds
what read-path tuning can recover in decode and in token-major tails.

## Adding a row

1. `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` from
   the StarForge checkout passes (quality against upstream at the merge-base).
2. `git worktree add ../sf-ds4-1flash-start <start commit of the current segment>`.
3. `python3 speed-bench/ab_bench.py --a ../sf-ds4-1flash-start --b . --kinds
   <the kinds of the change's phase> --guards <the guards>` exits 0 (tokens
   identical to the start, every headline metric of the selected kinds with
   two pairs or more). Use `--bitwise` when the change claims bit-identical
   output. Pool several invocations with `ab_pool.py` when one budget gives
   too few pairs for the claim.
4. Paste the printed row at the end of the current segment. The `step` cell is
   B's branch; the last row of a segment is where the work has got to. Cells
   of kinds not run stay empty.

## Segments

A segment starts with an A/A run on its start commit. A sync that changes
greedy output makes the token gate against the old start commit fail by
design; it then opens a new segment with a new start row, and the previous
segment's rows stay as they are.

### Segment 1

Start commit: the `main` commit on which `20-perf-bench-harness` lands (the
first whose bench has `--frontiers` and `--cache-stats`). Its row is an A/A
run on a worktree of that commit (`--a` and `--b` both the worktree), written
by `30-decode-layer-queue`.

| step | date | B commit | model | valid pairs | correctness | decode 2048 | decode 8192 | ttft 2500 | ttft 3500 | ttft 5000 | ttft 7500 | ttft 10000 | append +300 | append +1500 | guard ttft 16896 | guard decode 2500 | e2e |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| start (A/A) | 2026-09-28 | 7dea5e3 | DeepSeek-V4.1-Flash-Q2.gguf | 6 | PASS | 17.5 (+1.0%) | 18.1 (-1.1%) | 42.5 (+0.9%) |  | 68.7 (-0.5%) |  |  |  |  |  | 18.6 (-1.6%) | 107.9 (+0.1%) |
| 30 decode layer queue | 2026-09-28 | 7dea5e3 + S1 | DeepSeek-V4.1-Flash-Q2.gguf | 6 | PASS (bitwise) | 20.1 (+13.1%) | 20.0 (+13.3%) | 39.7 (+8.4%) |  | 65.8 (+8.7%) |  |  |  |  |  | 21.1 (+15.1%) | 99.9 (+8.8%) |
| 40 SSD expert reads | 2026-09-29 | 5410123 + 40 | DeepSeek-V4.1-Flash-Q2.gguf | 6 | PASS (bitwise) | 21.6 (+30.5%) | 20.2 (+13.4%) | 38.6 (+12.5%) |  | 64.5 (+12.2%) |  |  |  |  |  | 20.6 (+15.9%) | 97.0 (+14.8%) |
| 60 prefill sweeps | 2026-09-30 | 2c733ca + 60 | DeepSeek-V4.1-Flash-Q2.gguf | 19 | PASS (bitwise) |  |  | 33.7 (+26.1%) | 17.2 (+91.0%) | 63.1 (+13.4%) | 23.2 (+85.2%) | 38.3 (+3.2%) | 14.9 (+10.9%) | 11.8 (+44.2%) | 59.1 (+8.6%) | 21.2 (+14.7%) | 99.1 (+10.8%) |

`30-decode-layer-queue` keeps one step, #1041's `bd6f912` (queue the decode
layers on one box, commit each without waiting). Its 95% intervals: decode
2048 +12.0..+14.2%, decode 8192 +11.9..+14.7%, ttft 2500 +7.7..+9.2%, ttft
5000 +8.0..+9.4%, all clear of the A/A row. The same-engine schedule bench
agrees: 19.90 -> 23.06 t/s (+15.9%), 273 logit rows bit-identical. The
variant from #1073 (`2a281b0` + `29ce271`: flush every second layer, second
Engram table, no layer-13 drain) measured against it at decode 2048 -3.5%,
decode 8192 -2.0% (one valid pair), ttft 2500 -0.9%, ttft 5000 -0.6%, guard
-0.8%, and was reverted.

The first run after a `--quality --ssd-streaming` CLI run took 780-810 s
instead of about 75 s, twice out of two: that run maps whole layers and
leaves the page cache full. The warm-up absorbs it, but it spends the budget
and the invocation ends inconclusive. Keep `--quality` runs out of the chain
before a harness invocation.

`40-ssd-expert-reads` (row above, against the same start, so it carries `30`
too) measured every step and setting with `ab_bench.py`, D3 shape (`decode`,
`append`, `cold-5000`, guard `guard-decode`, `--bitwise`, 2700 s), sweeps on one
tree with `--b-env`. Correctness steps: #570's pool counters against `main`,
and #1125 against them, both bitwise with no headline interval below zero;
#1125 costs the first token after a sweep about 110 ms (first token 2048
-5.8%). Settings, pooled over the invocations named:

| Setting (B) against A | Invocations | decode 8192 | append +300 | ttft 5000 | Verdict |
|---|---|---|---|---|---|
| read-ahead off | 1 | -0.1% | +0.0% | -0.2% | dropped (all three at or below zero) |
| pread split 4 against 1 | 2 | -0.5% (-0.80..+1.10) | +0.90% (+0.20..+2.42) | +0.76% (+0.42..+2.24) | kept, default 4 |
| pread split 8 against 4 | 1 | -1.0% (-1.4..-0.5) | +0.3% | +0.6% | dropped (decode wholly below) |
| pread threads 18 against 9, at split 4 | 2 | -0.60% (-2.33..+1.02) | +0.35% | +0.66% (+0.44..+1.37) | kept, default 18 (append +1500 +1.27%) |
| split 4 + threads 18 against the S2 tree | 3 pooled with split 4 | +0.30% | +0.85% (+0.25..+2.42) | +0.54% | the step kept |
| slab residency set on | 2 | -0.37% (-0.84..-0.10) | -0.12% | +1.87% (+1.21..+4.84) | kept by the owner as an exception: first token 2048 +82.6%, 8192 +34.8%, e2e +0.9% |

Not measured, by design D7 after the Read path: slabs off and slab size (no
read-time term), `F_NOCACHE` (gives up the page cache the reads use).

`50-ssd-miss-overlap` adds no row: its one code step, #952 `a3043bb`'s early
load (the selected ids read before the shared expert, so a layer's preads run
while the GPU computes it), was bitwise and neutral against `main`, two
invocations pooled: decode 8192 -0.46% (-1.16..+0.25), decode 2048 -1.24%,
append +300 -0.10% (-0.25..+0.45), ttft 5000 +0.02% (-2.49..+0.70). It was
reverted, and the dead `prefetched` consumer it would have fed was deleted.
#849 stayed closed by its gate (Read path, after `40`). The tree that lands
differs from `40`'s only by that unreachable code, so its row is `40`'s.

`60-prefill-sweeps` measured each step against the previous one with
`ab_bench.py`, `--bitwise`, 3600 s; every step was bit-identical. S1a and S1b
change which sweep seeds the decode cache (hit rate 0.51 -> 0.32 after a
3.5K or 7.5K prompt), so they run with `--cache-policy-change`: without it the
first S1a invocation dropped every 3500 and 7500 pair. The S4 kernel steps are
decided on GPU section time (`--sections`, added as the change's tool step;
its A/A at 2048 rows read -0.4%, -1.8..+2.1). Pooled 95% intervals:

| Step (B) against the previous | Invocations | Target metrics | Other | Verdict |
|---|---|---|---|---|
| S1a one sweep for a batched tail (`798c64f` net, pos > 0 minimum) | 2 | ttft 3500 +79.3% (+70.8..+81.7), ttft 7500 +39.4% (+38.1..+40.2) | ttft 5000 +0.1%, append +0.5% / +0.5%; first token 3500 -1.5%, 7500 -3.9% (colder cache, inside ttft) | kept |
| S1b decoder suffix from 2541 rows | 1 | ttft 3500 +2.6% (+1.7..+4.1), ttft 5000 +2.2% (+1.6..+3.0), ttft 7500 +30.2% (+29.7..+30.3) | guard 16896 +0.6%, guard decode -0.4% | kept |
| S2a `1011874` ratio-1 batch publish | 1 | ttft 2500 +0.6% (+0.3..+1.1), 5000 +0.4% (+0.2..+1.0), 7500 +2.3% (+0.1..+5.4) | 3500 +1.0%, 10000 +1.2% | kept (deletes a line) |
| S2b `ce5a812` batched candidate blocks | 2 | ttft 7500 +1.69% (+0.77..+3.26) | 2500 +0.62%, 3500 +0.09%, 5000 +0.13%, 10000 +0.43%, all across zero | kept |
| S2c `3b7f8f2` select-all short index rows | 1 | ttft 7500 +4.3% (+3.3..+9.7) | 2500 +1.3%, 3500 +0.9%, 5000 -0.2%, 10000 -0.6%, all across zero | kept |
| S3 `bac91c2` + `c12d639` explicit expert buffers | 1 | ttft 2500 +14.2% (+13.7..+15.1), append +1500 +42.6% (+36.0..+43.5) | append +300 -0.17% (-0.30..+0.03), guard decode +1.1%, cache counters equal | kept |
| S4a #758 `heads16_dual_rb16` | 1, sections | `attention core/index` share: 2048 rows (`cold-2500`) -2.0% (-3.6..-0.7), 1452 rows +3.0% (+0.8..+4.5), 2048 rows (`cold-3500`) +1.4% (-5.9..+4.1) | ttft 2500 +1.9% (+0.1..+2.6), ttft 3500 -0.0% | dropped (slower at one shape) |
| S4b #864 IQ2_XXS half LUT | 1, sections | `shared/routed ffn` share: 2048 rows (`cold-2500`) -3.8% (-4.1..-2.9), 1452 rows -2.4% (-3.1..-1.0), 2048 rows (`cold-3500`) +8.5% (+2.6..+11.6) | ttft 2500 +0.1%, ttft 3500 -1.1% | dropped (slower at two shapes) |

The `60` row is against the segment start, so it carries `30` and `40`; kinds
`cold` and `append`, guards `guard-decode` and `guard-16896`,
`--cache-policy-change`, 19 valid pairs. Its 95% intervals: ttft 2500
+25.0..+27.6%, ttft 3500 +89.8..+92.1%, ttft 5000 +12.5..+14.2%, ttft 7500
+79.9..+96.2%, ttft 10000 +1.5..+5.4%, append +300 +10.4..+11.5%, append +1500
+42.6..+45.9%. The decode kinds were not run: no step of `60` touches decode,
and the guard reads 21.2 t/s (+14.7%), `40`'s +15.9% within the A/A band.
