# Performance record

Where the performance work on this child started, and where it has got to.
Each row is one `speed-bench/ab_bench.py` run, pasted from the `record row:`
line of its summary. A cell reads `B median (gain)`: the candidate's absolute
median under SSD streaming with the fixed 75 GiB expert cache, and its gain
against the segment's start commit, measured in the same session; positive is
faster for every metric (tokens/s up, seconds down). The gain is the figure to
read; the absolute numbers depend on the page cache, the room and the
machine's power mode.

## Rejected ideas

Measured on this machine and dropped. Read this before proposing one of them
again: a retry needs a reason the measurement below does not cover. The full
figures are in the named section.

| Idea | Why it does not help here | Section |
|---|---|---|
| Decode Q8 matvecs: rows per threadgroup (NR0 1/2/4), output exact | The gap to the vocabulary head's 605 GB/s comes from NSG and dispatch size. Changing NSG changes the summation order. The best row mix predicted 0.16 ms per token and measured decode 2048 -0.57% (CI below zero). | Decode kernels after 70 |
| Faster decode indexer scorer (#1061 rewrite) | 0.18 ms per token at 2K and 0.45 ms at 8K, under the harness resolution. It matters only past 32K. | Decode kernels after 70 |
| Faster routed-expert kernels for 2048-row prefill sweeps (prompts up to about 5K) | The sweep waits on SSD reads: about 250-330 ms per layer against about 100 ms of GPU. Any kernel gain becomes read wait. | Prefill routed experts after 80 |
| Expert-local / Morton threadgroup order in `kernel_mul_mm_id_mpp_packed` | The routed share is 3-5% slower at every chunk shape (CI below zero). The default order already reuses well. | Prefill routed experts after 80 |
| Cooperative-tensor (register) weight inputs for the packed MPP kernel | Exact, but it needs four per-simdgroup ops: the routed share is 2.3-3x slower and ttft 7500 -26%. | Prefill routed experts after 80 |
| Paired gate/up MPP with a fused SwiGLU epilogue | Ceiling about 0.2 s of ttft 10000 and nothing at 2048-row sweeps. Register headroom cannot be shown with the installed tools. | Prefill routed experts after 80 |
| Live-entry index for expert-cache victim scans (#621 `61e35e2`) | A scan of 15360 entries costs 0.05 ms, at most 0.7% of a short-answer token and 0.1% of a long one; the upstream index is 722 lines. | Expert cache after 100 |
| Global LRU instead of decayed hotness for expert-cache victims | Never fewer misses (decode +0.6%, append +0.2%, long answer equal). The avoidable misses come from seeds and decode replacing each other, which only route foresight could prevent. | Expert cache after 100 |
| Faster Engram conversion (lookup table, NEON) | Conversion costs under 1 us of a row whose read costs 0.66 ms; a few ms per sweep. | Engram reads after 110 |
| Engram cross-partition dedup or a raw-row cache | Duplicates are 4-8% of rows and already read once per partition; the sweep waits 0.2-0.8 s on Engram in total. | Engram reads after 110 |
| More Engram readers (32 or 64 instead of 16) | Exposed wait 0.37-0.40 s against 0.43 s on `cold-2500`, inside noise: the drive is shared with expert reads at full rate. | Engram reads after 110 |
| Judging a kernel from back-to-back single timeline runs | Thermal drift is larger than the effect: the same baseline read 29 and 39 ms per dispatch. Use the harness's sections mode. | Prefill routed experts after 80 |

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

## Decode kernels after 70 (2026-10-03, `80-m5-decode-kernels` S0)

`main` at `6da9533`, harness streaming flags. Kernel times come from
`DS4_METAL_ENCODER_TIMELINE` (one compute pass per dispatch group, so each
duration is an upper bound), 64 decoded tokens per frontier; the waits and
reads from an uninstrumented `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1`
run, 256 tokens minus 16. Every figure is per token.

| | 2048 | 8192 | 32768 (diagnostic) |
|---|---|---|---|
| uninstrumented decode | 40.9 ms (24.5 t/s) | 41.5 ms (24.1 t/s) | 48.4 ms (20.7 t/s, instrumented run) |
| GPU busy, sum of passes | 32.9 ms | 35.5 ms | 35.5 ms |
| q_b + RoPE, 1280 -> 32768 (`bf16_rope`) | 3.61 ms, 494 GB/s | 3.88 ms | 3.77 ms |
| output_b and shared down + HC expand (`bf16io_hc_expand4`, 80 per token) | 4.90 ms, 466 GB/s | 5.10 ms | 5.04 ms |
| grouped output_a, 8 x 4096 -> 1024 (`attn_out_low`) | 2.74 ms, 520 GB/s | 2.85 ms | 2.83 ms |
| shared gate/up SwiGLU, 5120 -> 2 x 2304 (`shared_mid_swiglu`) | 2.55 ms, 393 GB/s | 2.61 ms | 2.58 ms |
| q_a/kv pair, 5120 -> 1280 + 512 (`bf16_pair`) | 0.99 ms, 393 GB/s | 1.05 ms | 1.04 ms |
| vocabulary head, 5120 -> 129280 (NSG 8) | 1.16 ms, 605 GB/s | 1.21 ms | 1.19 ms |
| routed experts (IQ2_XXS gate/up + Q2_K down) | 6.71 ms | 8.08 ms | 6.82 ms |
| indexer scorer (`glm_indexer_score_one_direct`, 8 per token) | 0.18 ms | 0.45 ms | 1.37 ms |

At 2048 the per-layer wait at the selected-id readback (`sync`) is 32.7 ms
of the 40.9, pread 2.9 ms (968 dispatches of 0.71 ms over 240 tokens) and
binding 4.2 ms: decode is the GPU running, and kernel time reaches the
token.

The gate (design D1: an optimistic removal bound above the A/A resolution):
- **dense rows, open.** The five per-layer Q8 families take 14.8 ms at
  2048. They read 6.9 GB per token at 390-520 GB/s; the vocabulary head
  shows the same Q8 walk reaching 605 GB/s. At 600 GB/s they would take
  11.5 ms, 3.3 ms (about 8%) less.
- **indexer rows, closed.** The scorer is 0.4% of the token at 2048 and
  1.1% at 8192; removing a third of it is 0.1-0.4%, under the harness
  resolution. It only grows past 1 ms at 32K, outside the target mix, so
  `80`'s indexer step (tasks 3.x) does not run.

Current noise, an uninstrumented A/A on `6da9533` (`--kinds decode,append
--bitwise --budget 1800`, 10 valid pairs, bitwise, thermal state Heavy,
GPU median 1242 MHz): decode 2048 -0.9% (-2.6..+0.6), decode 8192 -0.9%
(-1.6..+0.0), append +300 +0.2% (-0.1..+0.4), append +1500 +0.3%
(-1.3..+0.7). A step therefore needs about 1-1.5% on decode to show in
one invocation.

The dense step (design D2) made the five families templates over output
rows per threadgroup (1, 2, 4; RoPE 2, 4), with the K walk, NSG 4,
reduction and BF16 stores unchanged. A fixture showed every grouping
bitwise against the two-row kernels, odd tails and edge values included.
Kernel time at 2048 (timeline, two runs per grouping, change against 2 rows):

| Family | 1 row | 4 rows |
|---|---|---|
| q_b + RoPE | - | -1.4% |
| output_b / shared down + HC expand | +2.3% | +1.2% |
| grouped output_a | -1.5% | -0.6% |
| shared gate/up SwiGLU | -1.2% | +1.5% |
| q_a/kv pair | -4.0% | -3.0% |

The best mix (RoPE 4, expand 2, the rest 1) predicts about 0.16 ms per
token. Row grouping does not close the gap to the vocabulary head's rate:
what separates them is NSG (K partitioning, so the summation order) and
the size of the dispatch, neither of which an exact change may touch.

| Step (B) against the previous | Invocations | Target metrics | Other | Verdict |
|---|---|---|---|---|
| S1 output rows per threadgroup, RoPE 4 / expand 2 / output_a, shared, pair 1, against `6da9533` | 2 (6 + 20 pairs) | decode 2048 -0.57% (-1.00..-0.10), decode 8192 +0.14% (-0.24..+0.51) | append +300 -0.05% (-0.28..+0.07), append +1500 +0.22% (-0.83..+1.94); guards once: ttft 2500 +2.4%, 3500 +2.2%, 5000 +0.6%, 7500 +3.3%, 10000 +2.7%, guard ttft 16896 -2.7%, guard decode +0.8%; bitwise | dropped (decode 2048 below zero) |

Runs: `80-s1.1` (`--guards cold,guard-16896,guard-decode`, budget 3000)
and `80-s1b.2` (decode, append, budget 3600), both with
`--b-env DS4_METAL_V41_Q8_NR0=42111`. With both gates closed, `80` lands
no runtime code: this section is its record.

## Prefill routed experts after 80 (2026-10-03, `90-m5-prefill-tensor-locality` S0)

`main` at `cc511df`, harness streaming flags, 16 generated tokens. V4.1
prefill passes `force_resident` to the routed batch, so every chunk of
512-8192 rows runs `kernel_mul_mm_id_{iq2_xxs,q2_K}_mpp_packed`; streaming
chunks stop at 4096 rows, so the `_m32n128` variants are never dispatched
here. Per-layer read wait (`map`) and GPU drain come from
`DS4_METAL_GRAPH_PREFILL_PROFILE`, kernel times from
`DS4_METAL_ENCODER_TIMELINE`, the routed stages from
`DS4_METAL_MOE_STAGE_PROFILE`, all summed over the 40 layers of a sweep.

| Prompt | Sweeps | Read wait | GPU drain | Routed gate / up / down | ttft (that run) |
|---|---|---|---|---|---|
| 2500 | 2048 rows, then 452 tokens at decode rate | 3.29 s | 4.33 s | 0.51 / 0.59 / 0.51 s | 31.1 s |
| 5000 | 2 x 2048 rows, then 904 tokens | 2.16 s | 6.06 s | 0.89 / 0.82 / 0.82 s | 55.5 s |
| 10000 | 8192-row wide sweep (4096-row chunks), then 1808 rows | 2.79 s, about 0 in the 4096-row chunks | 26.5 s | packed kernels 5.40 s, RHS packing 0.23 s | 38.7 s |
| append 5300 -> +1500 | 1500 rows | 3.58 s | 4.12 s | - | - |

The gate (design D1):
- **2048-row sweeps, closed.** Reading the next layer's experts takes
  about 250-330 ms against about 100 ms of GPU work plus the cache seed;
  the read wait is above zero in 33 of 40 layers. A faster routed kernel
  only lengthens the wait, so ttft 2500, 3500 and 5000 cannot move.
- **wide sweeps, open.** At 4096-row chunks the GPU is the critical path
  and the packed kernels are about 14% of ttft 10000; ttft 7500 is one
  wide sweep of the same kind.
- Outside `90`'s zone, for `100`: in the serialized section profile of the
  1808-row sweep that follows the wide one, `attention projections` take
  9.3 s of 15.8 s (59%), against 6.6% in the 4096-row chunks.

Back-to-back single timeline runs cannot judge a kernel step: two runs of
the same baseline read 29.0 and 39.2 ms per 4096-row gate dispatch, and a
first D2 run that looked 24% faster was the machine running cooler. Every
step below was decided by the sections mode (`--sections "shared/routed
ffn"`, kinds `cold-2500,cold-7500,cold-10000`, `--bitwise`, 3600 s). A
negative gain means the routed share of GPU time grew.

| Step (B) against `cc511df` | Invocations | Routed share | Other | Verdict |
|---|---|---|---|---|
| S1 expert-local traversal (D2): consecutive threadgroups take every output tile of one work item | 1 (43 pairs) | 2048 rows (`cold-2500`) -5.2% (-8.8..-4.0), 1356 rows -4.0% (-5.2..-1.2), 1808 rows -4.8% (-5.6..-2.9), 4096 rows -3.2% (-4.4..-2.3) | ttft 2500 +1.5% (-0.2..+2.6), ttft 7500 -1.2% (-2.9..+0.4), ttft 10000 +0.4% (-1.8..+0.9); bitwise | dropped |
| S2 cooperative-input weights (D3): four per-simdgroup 32x16x32 matmuls fed from registers, no threadgroup staging or barrier | 1 (41 pairs) | 2048 rows -69.3% (-71.0..-68.4), 1356 rows -61.1%, 1808 rows -60.9%, 4096 rows -63.7% (-63.8..-62.8) | ttft 2500 -6.1%, ttft 7500 -26.4%, ttft 10000 -20.3%; bitwise | dropped |

S2 was exact. A probe showed the per-simdgroup ops bitwise against the
`execution_simdgroups<4>` op, and the fixture passed every shape with a
planted wrong element caught. The right-input layout gives each lane two
rows (r, r+8) times two runs of four K values (k, k+16), so the weights
were dequantized by fours with the arithmetic of `dequantize_*`. The
pipelines report 1024 threads per threadgroup before and after, so the cost
is instructions, not occupancy. The Metal compiler silently omits a kernel
instance whose template argument is a `static` function: the library
builds and the lookup fails at run time.

The paired gate/up epilogue (D4) did not run. Its ceiling is the
`swiglu_weight_f16` pass (77 ms), the mid packing (29 ms) and the f32
gate/up stores inside the matmuls: about 0.2 s of ttft 10000 and nothing at
2048-row sweeps. The register headroom it requires cannot be shown with the
installed tools. `90` lands no runtime code: this section is its record.

## Prefill weight delivery after 90 (2026-10-03, `100-prefill-weight-delivery` S0)

`main` at `86bac78`, harness streaming flags, 16 generated tokens, one run
per shape with `DS4_METAL_GRAPH_PREFILL_PROFILE` and a temporary probe that
counted, when each layer's read starts, how many of the next layer's 384
experts are ready in the decode cache (valid, not in flight). A layer's
routed experts are 3.56 GiB (384 x 9.49 MiB). All times are summed over the
40 layers of a sweep; `map` is the exposed wait for the layer's weights.

| Sweep | Weights | map | GPU drain | seed | next layer in RAM |
|---|---|---|---|---|---|
| 2500: 2048 rows | explicit buffers | 3.75 s | 4.36 s | 3.65 s | 0 of 384 |
| 3500: one wide sweep, 2048-row tiles | mmap page-in | 2.34 s | 8.35 s | 4.19 s | 0 |
| 5000: 4096-row wide sweep | mmap page-in | 2.70 s | 8.66 s | 4.24 s | 0 |
| 7500: one wide sweep, 2048-row tiles | mmap page-in | 1.86 s | 12.8 s | 4.10 s | 0 |
| 10000: 8192-row wide sweep | mmap page-in | 2.65 s | 13.7 s | 3.41 s | 0 |
| 10000: then 1808 rows | explicit buffers | 0.33 s | 14.7 s | 0.33 s | 201 |
| append 5300 -> +1500: 1500 rows | explicit buffers | 4.51 s | 6.23 s | 0.18 s | 102-161, about 135 |

Two facts set the stages:
- **The decode cache starts empty.** V4.1 has no popularity preload (the
  hotlist belongs to the old `ds4_gpu_graph`), so in a fresh process the
  only entries are those the current sweep's seeds wrote, all for layers
  already passed. The first sweep of every `cold` kind finds none of the next
  layer in RAM. A later sweep finds the 201 experts per layer the previous
  seed kept (52%), fewer after decode has replaced some (about 35% after
  the 300-token append and 16 generated tokens).
- **Reads still bound the explicit sweeps.** At 1500-2048 rows a layer
  read takes about 280 ms (13.6 GB/s) against 170-300 ms of engram, GPU and
  seed; the wait is above 5 ms in 32 of 40 layers.

Recoverable cost per stage:
- **D2, wide-sweep lifetime:** the mmap page-in sweeps of 3500, 5000, 7500
  and the first 10000 sweep wait 1.9-2.7 s for weights, mostly in the
  decoder layers where few suffix rows leave little GPU work to hide the read,
  and their seed reads mapped pages. At 2048 rows the explicit buffers
  gained 14.2% ttft 2500 over the same page-in (`60` S3). Open.
- **D3, RAM before disk:** zero for every `cold` kind (nothing of the next
  layer is cached), about a third of each layer's bytes for append +1500
  (4.51 s of waiting at about 280 ms per read), and about half for the
  second 10000 sweep, whose 0.33 s wait leaves little. Open for append only.
- **D4, native I/O:** decided after D2 and D3, on the wait that remains
  (closed, below).

Each step against the previous kept state, `ab_bench.py`, `--bitwise`, 3600 s:

| Step (B) against the previous | Invocations | Target metrics | Other | Verdict |
|---|---|---|---|---|
| S1 explicit buffers for wide sweeps (D2): admission drops the 2048-row and non-wide limits, a slot stays bound through every tile of its layer | 1 (34 pairs) | ttft 3500 +23.3% (+22.0..+25.0), ttft 5000 +8.5% (+7.9..+9.7), ttft 7500 +19.0% (+17.5..+20.8), ttft 10000 +23.9% (+21.9..+25.7) | first token after the sweep 3500 1373 -> 258 ms, 7500 1372 -> 297 ms, 10000 164 -> 125 ms; guards once: decode 2500 +1.3%, append +300 -1.6%, append +1500 +1.7% (unchanged paths), 16896 pair dropped (GPU clock); hit rates equal | kept |
| S2 RAM before disk (D3): ready, not in-flight cache entries of the next layer are blitted into its slot without a hit, recency or hotness update; the workers read only the remaining experts, adjacent ones merged; the seed and every join wait for the copy | 1 (28 pairs) | append +1500 +34.8% (+25.6..+37.2) | append +300 -0.1% (-0.5..+0.3), prefill 5000 +0.3%, ttft 2500 +0.2% (-0.1..+0.5), ttft 7500 +0.5% (+0.2..+1.6); guards once: decode 2500 +0.5%, 16896 -0.7%; hit rates and the `--cache-stats` counters equal | kept |

In the append +1500 sweep S2 copied 63.3 GiB from RAM and read the other
79.1 GiB of its 40 layers from disk (44% and 56%); the exposed wait fell
from 4.51 s to 0.87 s in a profiled run. The `cold` sweeps copy nothing (the
cache holds no later layer), and their unchanged ttft shows the reworked
worker split costs nothing.

D4 (native Metal I/O) closed at its gate. A timer in the readers of a
`cold-2500` sweep measured 245.7 ms per layer (175-274), against 230-257 ms
for a bare `F_NOCACHE` pread of the same 3.82 GB with 8, 18 or 32 threads
(15-16.6 GB/s). The reads already run at the drive's rate; an I/O queue
could remove only host scheduling, which is not there. What remains of the
wait is bandwidth: a cold 2048-row sweep needs 40 x 3.82 GB from disk.

## Expert cache after 100 (2026-10-04, `110-expert-cache-efficiency` S0)

`main` at `896785c`, harness streaming flags, one run per shape with
`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`, `DS4_MOE_RECORD_SELECTED_IDS`
and a temporary probe that marked every evicted (layer, expert) and counted
the later misses on a marked one ("re-misses"). Misses are deterministic:
two runs of a shape read the same counts. The cache report's misses include
the prefill seeds' installs; the decode misses below exclude them.

| Shape | Victim scans | Scan time | Decode misses | Re-misses | Replay from empty: distinct pairs / LRU / Belady |
|---|---|---|---|---|---|
| decode 2048 + 8192, 256 tokens each | 3135 x 15360 entries | 162 ms (0.05 ms each) | 2197 | 943 (705 after the 8192 sweep) | 7852 / 7852 / 7852 |
| append 5000 -> 5300 -> 6800 | 5878 | 255 ms | 5500 | 2707 | 10088 / 11054 / 10088 |
| decode 8192, 2500 tokens | 1817 | 80 ms | 2499 | 285 | 7556 / 7556 / 7556 |

The gates (design D1):
- **D2, live-entry index, closed.** A scan costs 0.044-0.052 ms; at most
  0.3 ms of a 42 ms token in short answers (0.7%) and 0.03 ms in the long
  one. An index halves the entries a scan visits but cannot reach the
  harness's resolution, and #621 `61e35e2` changes 722 lines of
  `ds4_metal.m`, so it would need +1.5%. Not implemented.
- **D3, global LRU, tried and closed.** The re-misses bound what any
  eviction policy could save: about 1.8 per token after a sweep in short
  answers and 3.1 in the 300-token append (a few percent at about 0.7 ms a
  miss), 0.1 in the long answer. They come from the prefill seeds replacing
  decode-hot experts and back. The simulator starts empty and sees no seeds,
  so its bounds do not apply: production misses fewer than its compulsory
  count. LRU (hotness held at zero, so every victim comparison falls to
  `last_used`) missed 13977 against 13892 in decode, 16016 against 15979 in
  append and the same 9985 in the long answer: never fewer, so it cannot be
  faster, and no harness run was spent on it. Avoiding the re-misses needs
  to know the future routing, which the design excludes.

`110` lands no runtime code: this section is its record.

## Engram reads after 110 (2026-10-04, `120-engram-read-efficiency` S0)

`main` at `631fdda`, harness streaming flags, one run per shape with
`DS4_METAL_GRAPH_PREFILL_PROFILE` and temporary timers in `ds4_engram.c`
(time in `pread` and in conversion per row, summed over the 16 readers, and
the rows served by the in-partition duplicate copy) and around the two
decode joins. Rows are 264 bytes (256 E4M3 codes and 8 E8M0 scales).

| Shape | Rows read | Duplicates | `pread`, thread sum | Conversion, thread sum | Exposed in the sweep | Decode wait per token |
|---|---|---|---|---|---|---|
| cold-2500 (2048-row sweep, 452 token-major) | 115787 | 4981 (4.3%) | 75.9 s (0.66 ms/row) | 0.10 s (0.86 us/row) | 0.43-0.76 s (layer 1 and 14) | 0.054 ms |
| cold-7500 (one wide sweep) | 334616 | 26152 (7.8%) | 52.6 s | 0.24 s | 0.19 s | - |
| append 5000 -> 5300 -> 6800 | 309383 | 19321 (6.2%) | 91.7 s | 0.26 s | 0.16 s, then 0 at +1500 | 0.037 ms |
| decode 2048 + 8192, 256 tokens each | 387989 | 29803 (7.7%) | 115.3 s | 0.32 s | 0.44 s, then 0.05 s | 0.016 ms |

Each row costs 0.66 ms of read latency against under 1 us of conversion: a
prefill's Engram reads share the drive with the expert reads, which run at
its full rate. What the sweep waits for is that latency, mostly at layer 1
(only layer 0 hides table 0) and layer 14.

The gates (design D1), all closed:
- **D2, conversion:** under 0.5% of the readers' time, a few ms of wall
  time per sweep. A lookup table or NEON cannot move ttft.
- **D3, deduplication and row cache:** duplicates are 4-8% of rows and are
  already read once inside each of the 16 partitions; a cross-partition run
  can only repeat at the 15 boundaries of a 2048-token batch. A cross-batch
  cache could save at most a similar share of a wait that is 0.2-0.8 s per
  sweep: below the harness's resolution.
- **D4, prefetch lifetime:** the prefix-sized output is
  `carry_cap x 24 x 256 x 4` bytes, 768 MiB at ctx 32768, inside the static
  context. A two-tile ring would only save memory, and the harness holds
  the expert cache fixed, so it cannot win on speed.
- **Decode:** `70`'s asynchronous reads leave 0.02-0.05 ms per token.

Outside the design, a probe with 32 and 64 readers on `cold-2500` read
0.37-0.40 s of exposed wait against 0.43 s with 16: inside run-to-run noise.
Taking Engram reads off the expert drive is `150`'s question.

`120` lands no runtime code: this section is its record.

## Decode submission after 120 (2026-10-04, `130-m5-decode-submission` S0)

`main` at `bfa0ef2`, harness streaming flags. `DS4_METAL_GPU_BUSY_PROFILE`
over 16- and 272-token runs isolates 256 decoded tokens; `DS4_METAL_CB_TIMES`
(print limit lifted) and a probe stamping the CPU's return from each wait
against the command buffers' GPU times split the gaps; `sample` profiled the
main thread for 15 s of decode.

| Frontier | Token | GPU busy | GPU idle |
|---|---|---|---|
| 2048 | 40.9 ms | 28.5 ms | 12.4 ms (30%) |
| 8192 | 41.8 ms | 30.6 ms | 11.2 ms (27%) |

A token is 81 command buffers, two per layer. A (attention and router,
about 430 us of GPU) is waited so the CPU can read the six selected ids; B
(the routed experts and the rest of the layer, about 200 us) is encoded only
then. Nearly all idle time sits in front of B, 310 us on average per layer:

| Component | Per layer |
|---|---|
| CPU wake: A's `GPUEndTime` to the return of `waitUntilCompleted` | 76 us |
| CPU work: ids, cache peek, bindings, encode of B, commit | 111-118 us |
| Commit of B to its `GPUStartTime` | 103 us |

The main thread waits 90.7% of the time. Of its CPU samples, the pipeline
lookups (`stringWithFormat` in `ds4_gpu_get_mul_mv_pipeline` and the plain
getter) are about 1% of wall time, `getenv` 0.5% spread over many callers,
`F_RDADVISE` read-ahead 0.9% (dropped once by `40`). The gates:
- **D2, allocation-free lookup:** open. The fast-lookup cache existed but
  only the pre-M5 MXFP4 graph armed it; V4.1 decode inserts 21 pipelines,
  well inside its 64 slots.
- **D3, coalescing:** closed. Between B and the next A the gap is 1 us (A is
  committed while B runs); the only gap is the selected-id readback, which
  coalescing cannot cross.
- The wake and commit-to-start components are outside this design: `131`
  (bounded poll at the readback) and `132` (expert pass committed ahead and
  gated by a shared event) are written for them.

Each step against the previous kept state, `ab_bench.py`, `--bitwise`, 3600 s:

| Step (B) against the previous | Invocations | Target metrics | Other | Verdict |
|---|---|---|---|---|
| S1 allocation-free pipeline lookup for V4.1 decode (D2, #1067 `d1738d2`'s plain getter): the step arms the existing fast cache, plain names keyed with a sentinel nsg | 2 pooled (22 pairs) | decode 2048 +0.42% (+0.28..+0.63), decode 8192 +0.23% (+0.02..+0.67) | append +300 +0.46% (+0.00..+0.69), append +1500 +1.75% (+1.46..+3.41), prefill 5000 +0.08% (-0.06..+0.37); guards once: decode 2500 +0.6%, ttft 2500 -0.1%; hit rates equal | kept |

## Readback wait after 130 (2026-10-04, `131-decode-readback-spin-wait`)

`main` at `b59c5dd`, `130`'s probe (CPU return from the wait against the
command buffers' GPU times), decode 2048 and 8192 with 256 tokens: per layer
72 us wake, 120-128 us CPU work, 104 us commit to GPU start. The gate
(over 20 us of wake) is open.

Primitives tried at the selected-id readback, single runs:
- **Polling `cb.status`** with `yield` for up to 2 ms before
  `waitUntilCompleted`: wake 72 -> 48 us. The status turns Completed about
  45 us after the GPU ends, so this is the floor for any command-buffer wait.
- **The shared-event path** that Q4 uses (`ds4_gpu_signal_batch_and_wait_event`),
  blocking or polled: decode fell to 2.8 tokens/s on the IQ2/Q2 path. Not
  investigated further; dropped.

| Step (B) against the previous | Invocations | Target metrics | Other | Verdict |
|---|---|---|---|---|
| S1 bounded status poll (2 ms) before the blocking wait, only at the streaming decode's selected-id readback | 1 (18 pairs) | decode 2048 +2.8% (+1.0..+3.8), decode 8192 +3.1% (+2.2..+4.8) | append +300 +4.5% (+3.3..+5.0), prefill 5000 +2.1% (+1.3..+3.6), append +1500 -0.4% (-1.9..+6.6); guards once: decode 2500 +3.7%, ttft 2500 +0.1%; hit rates equal | kept |

The gain exceeds the 24 us x 40 of shorter wake alone (about 2.3%): a
thread that does not sleep also resumes on a warm core.

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
| 70 decode glue fusions | 2026-10-03 | 0d88af9 + 70 | DeepSeek-V4.1-Flash-Q2.gguf | 12 + 33 | PASS (bitwise) | 20.5 (+23.6%) | 20.3 (+19.4%) | 32.4 (+37.5%) | 17.5 (+92.9%) | 62.3 (+21.4%) | 23.7 (+84.9%) | 39.9 (+2.2%) | 14.4 (+21.9%) | 11.9 (+43.7%) | 59.7 (+13.5%) | 21.0 (+22.1%) | 87.4 (+27.4%) |
| 100 prefill weight delivery | 2026-10-04 | 86bac78 + 100 | DeepSeek-V4.1-Flash-Q2.gguf | 13 + 41 | PASS (bitwise) |  |  | 32.0 (+34.4%) | 13.1 (+155.7%) | 55.4 (+32.2%) | 18.6 (+126.4%) | 27.8 (+46.7%) | 14.0 (+24.1%) | 8.14 (+106.7%) | 54.5 (+21.3%) | 22.3 (+27.6%) | 103.9 (+8.0%) |
| 130 decode submission | 2026-10-04 | bfa0ef2 + 130 | DeepSeek-V4.1-Flash-Q2.gguf | 12 + 33 | PASS (bitwise) | 20.4 (+19.5%) | 21.0 (+21.3%) | 29.8 (+42.9%) | 13.7 (+152.9%) | 48.5 (+40.4%) | 21.4 (+120.7%) | 26.2 (+49.0%) | 13.2 (+24.7%) | 8.33 (+110.9%) |  | 21.6 (+23.3%) | 89.4 (+21.3%) |
| 131 readback poll | 2026-10-04 | b59c5dd + 131 | DeepSeek-V4.1-Flash-Q2.gguf | 4 + 3 + 44 | PASS (bitwise) | 22.3 (+29.8%) | 22.5 (+28.1%) |  | 13.3 (+156.7%) |  | 18.9 (+125.8%) | 27.4 (+48.0%) |  |  |  |  | 94.3 (+18.3%) |

`100-prefill-weight-delivery` (row above, `80` and `90` landed no runtime
code) is two invocations against the start: `cold,append` with the guards
(13 pairs; 3500 and 7500 dropped every pair because `60`'s single sweep seeds
the cache differently, hit rate 0.51 -> 0.32), then `cold-3500,cold-7500`
with `--cache-policy-change` (41 pairs). Its e2e holds decode at the
reference, which `100` does not touch. Parity passed on the candidate tree
(10 prompts, token-identical). The steps are in the "Prefill weight delivery
after 90" section.

`131-decode-readback-spin-wait` (row above) is three invocations against the
start on an evening with the GPU throttling (thermal Heavy, runs down to
575 MHz): `decode,cold,append` with the guards kept 4 of 20 pairs, its
repeat on the kinds left empty 3 of 18, and `cold-3500,cold-7500` with
`--cache-policy-change` 44. Decode is pooled over the first two (5 pairs:
2048 +29.8%, +29.0..+37.2; 8192 +28.1%, +27.7..+28.8). The empty cells lost
every pair to the clock check; `131` does not touch prefill, whose figures
are `130`'s row. The e2e cell holds the unmeasured kinds at the reference.
Parity passed on the candidate (10 prompts).

`130-m5-decode-submission` (row above; `110` and `120` landed no runtime
code) is two invocations against the start: `decode,cold,append` with the
guards (12 pairs; 3500 and 7500 dropped for `60`'s cache seeding, the 16896
guard for the GPU clock), then `cold-3500,cold-7500` with
`--cache-policy-change` (33 pairs). Parity passed on the candidate tree
(10 prompts). Its decode figures are the first since `70` and carry `130`'s
+0.2-0.4%; the steps are in the "Decode submission after 120" section.

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

`70-decode-glue-fusions` measures each step against the previous kept one with
`ab_bench.py`, using `--bitwise`, 3600 s, kinds `decode,append,cold-2500` and
guard `guard-decode`. A second invocation runs only on `decode` when the
first is inconclusive. Pooled 95% intervals:

| Step (B) against the previous | Invocations | Target metrics | Other | Verdict |
|---|---|---|---|---|
| S1 `e768396` no candidate selection up to 2048 blocks | 2 | decode 2048 +0.00% (-0.64..+0.57), decode 8192 +0.21% (-0.21..+0.79) | append +300 +0.6%, ttft 2500 +0.2%, guard decode +3.2% | dropped (neutral, adds a line) |
| S2 `edceb7a` experts selected in one dispatch | 2 | decode 2048 +1.15% (+0.63..+1.50), decode 8192 +1.28% (+0.67..+1.73) | append +300 +2.4% (+1.6..+3.4), ttft 2500 +2.4% (+1.7..+3.0), guard decode +1.8%; `--decode-switch` exact | kept |
| S3 `d95f8b6` BF16 rounding inside the producing kernels | 2 | decode 2048 +1.14% (+0.79..+1.38), decode 8192 +1.14% (+1.02..+1.42) | append +300 +1.1% (+0.8..+1.5), append +1500 +1.6%, ttft 2500 +2.2% (+2.2..+2.4), guard decode +2.2% | kept |
| S4a `d8d1523` HC block input in one dispatch | 1 | decode 2048 +1.3% (+0.8..+1.4), decode 8192 +0.9% (+0.3..+1.6) | append +300 +1.4% (+1.4..+1.9), ttft 2500 +1.3% (+0.7..+1.4), guard decode +3.0%; `--decode-switch` exact for both switches | kept (479 lines) |
| S4b `d8d1523` paired q_a/kv projections, pair norm, q_b with RoPE | 2 | decode 2048 +0.36% (+0.14..+0.63), decode 8192 +0.47% (+0.38..+0.66) | append +300 +0.8% (+0.4..+1.3), ttft 2500 +1.2% (+0.4..+1.6), guard decode +1.3% | kept (447 lines) |
| S4c `d8d1523` + `1923131` RoPE, quantize and store in one dispatch | 2 | decode 8192 +0.80% (+0.52..+0.94), decode 2048 +0.43% (+0.00..+0.67) | append +300 +0.6% (+0.5..+1.2), ttft 2500 +0.8% (+0.0..+1.4), guard decode +0.0%; rope-quantize test and `--decode-switch` exact | kept (131 lines with the test) |
| S4d `d8d1523` attention with the selected rows gathered in its staging kernel | 2 | decode 2048 +0.71% (+0.48..+0.85), decode 8192 +0.72% (+0.43..+0.94) | append +300 +0.7%, ttft 2500 +1.2% (+0.2..+2.4), guard decode +2.5%; `--decode-switch` exact | kept (about 110 lines) |
| S4e `d8d1523` attention output and shared down fused into the HC expand, low projection with the inverse rope folded in | 1 | decode 2048 -1.4% (-1.9..-0.5), decode 8192 -0.9% (-1.1..-0.7) | append +300 -0.6%; with `DS4_METAL_DISABLE_V41_EXPAND_FUSION` on B, decode 2048 -2.1% (-2.6..-1.1), decode 8192 -1.6%: the rope-folded low projection is the slow part | dropped as a whole |
| S4e' the same without the rope-folded low projection | 2 | decode 2048 +0.66% (+0.49..+1.02), decode 8192 +0.69% (+0.57..+0.91) | append +300 +0.8% (+0.2..+1.2), ttft 2500 +1.1% (+0.5..+2.0), guard decode +1.9%; `--decode-switch` exact | kept (158 lines) |
| S4f `d8d1523` shared gate/up SwiGLU in one dispatch | 2 | decode 2048 +0.53% (+0.26..+0.68), decode 8192 +0.47% (+0.33..+0.71) | append +300 +1.4% (+0.8..+1.9), append +1500 +0.8%, ttft 2500 +1.6% (+0.4..+2.4), guard decode +1.5% | kept (70 lines) |
| S4g `d8d1523` Engram rows read on workers while the first layers encode | 2 | decode 8192 +1.20% (+0.82..+1.41), decode 2048 +0.59% (+0.05..+1.24), append +300 +1.30% (+1.14..+1.78) | append +1500 +1.5% (+0.4..+2.3), ttft 2500 +1.6% (+0.6..+2.7), guard decode +2.4%, guard ttft 5000 +0.1% | kept (53 lines) |
| S4 cumulative: the kept sites S4a-g together against the S3 tree (over 800 lines, needs +1.5%) | 1 | decode 2048 +5.7% (+4.3..+6.8), decode 8192 +6.2% (+5.4..+6.4) | append +300 +6.3% (+5.8..+6.7), append +1500 -0.4% (-0.9..+0.3), ttft 2500 +5.2% (+3.7..+6.0), guard decode +7.8% | passes; no site removed |
| S5 `4fbbc4a` head half: the vocabulary head encoded before the last drain | 2 | decode 2048 +0.19% (-1.09..+0.43), decode 8192 +0.16% (-0.07..+0.30), append +300 +0.07% (-0.09..+0.18) | ttft 2500 +0.7%, guard decode +2.0%, guard ttft 5000 -0.4%; `--decode-switch` exact | dropped (neutral, adds 11 lines) |

The `70` row is against the segment start (`7dea5e3`), so it carries `30`,
`40` and `60`. It comes from two invocations, both bitwise:
- kinds `decode,cold,append` with guard `guard-decode`, 12 valid pairs;
- `cold-3500,cold-7500` with guard `guard-16896` and `--cache-policy-change`,
  33 valid pairs.

The first invocation dropped every 3500 and 7500 pair on cache drift. That is
`60`'s schedule, whose single sweep seeds a colder cache, and it is why `60`
ran with the flag. The e2e is recomputed with every phase measured.

Its 95% intervals: decode 2048 +18.4..+29.1%, decode 8192 +18.3..+24.2%,
ttft 2500 +34.0..+41.1%, ttft 3500 +91.6..+95.8%, ttft 5000 +20.1..+22.6%,
ttft 7500 +82.5..+89.0%, ttft 10000 +1.3..+3.0%, append +300 +21.1..+22.6%,
append +1500 +42.6..+44.8%. Against the `60` row the decode kinds add about
20% here. Of that, `70`'s steps measured about 6% from S4 plus 1.15% (S2)
and 1.14% (S3) step by step; the rest is `30` and `40`, which the `60` row
did not run.
