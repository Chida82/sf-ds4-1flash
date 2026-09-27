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
| decode token at 8K (hit rate 0.932, 16 misses of 240 lookups) | 56 ms (17.7 t/s) | expert path 44 ms = 78%: waiting for missing experts' loads (`sync`) 38.0, bind 4.3, readahead 1.8, buffer prepare 0.2; the rest 12 ms is attention, Engram rows and host work. GPU busy 62% of the frontier (sweep included) |
| decode token at 2K (hit rate 0.868, 32 misses) | 58 ms (17.3 t/s) | the same path with twice the misses; the probe run itself read 5.1 t/s because `DS4_METAL_CB_TIMES` waits on every command buffer, so its split is not reported: never combine that probe with a timing |
| token-major prefill tail (904 tokens of `cold-5000`, hit rate 0.948) | 58 ms per token | expert path 43 ms = 74%: sync 35.1, bind 4.3, buffer prepare 2.2, readahead 1.8. A tail runs at the decode rate |
| first tokens after a wide sweep (16 tokens of `cold-10000`) | first 2.2 s, then 87 ms | per-layer hit rate 0.33-0.54 (mean 0.51): a wide sweep leaves the decode cache half cold, and the first token pays sync 131 ms and buffer prepare 109 ms per layer sweep-equivalent. After a token-major tail the first token costs 60-85 ms |
| 2048-row sweep from empty | 14.9-17.9 s | stages 9.1-10.2 s: shared/routed FFN 4.0-4.8, attention core/index 2.1-2.2, attention projections 1.0-1.3, HC/Engram 1.1-1.2, attention output 0.4-0.5, norms 0.3; outside stages 6-8 s (layer page-in and prepare between layers). GPU busy 45% of the `cold-2500` frontier |
| 6144-row wide sweep (`decode`'s +6144) | 26.9 s | three 2048-row tiles of 11.8, 5.3 and 5.7 s of stages (the first tile carries the Engram and projection costs, the later ones about 5 s: routed FFN 2, attention core 2); outside stages 4 s |
| 8192-row wide sweep plus 1808 chunk (`cold-10000`) | 41.4 s | two 4096-row tiles of 6.1 and 5.0 s of stages, the decoder suffix's per-layer shrinking tiles about 4 s, the 1808 chunk 10.3 s (routed FFN 5.0, attention core 2.0, Engram 1.3); GPU busy 45% |

Per-layer hit rate at 8K: 0.897 (layer 39) to 0.957, the last layers lowest;
at 2K: 0.824 (layer 0) to 0.886, the first layers lowest. Reads are page
cache warm: a miss's `pread` averages 0.54-0.68 ms for 9.49 MiB.

What the start gates read: `50-ssd-miss-overlap` targets the 38 ms of
`sync` per decode token, three quarters of the token; `70-decode-glue-fusions`
targets the remaining 12 ms; `60-prefill-sweeps` the 6-8 s outside the
stages of a sweep, the tail policy (a 904-token tail costs 53 s against 20 s
for one more sweep) and the half-cold cache a wide sweep leaves behind.

**Routing trace.** `cold-5000` with 2000 generated tokens and
`DS4_MOE_RECORD_SELECTED_IDS`: 116160 routed calls = 2904 tokens (the 904
token-major plus the 2000 decoded) over 40 MoE layers, 696960 lookups,
11088 distinct (layer, expert) pairs against 8078 slots. Replayed from an
empty cache by `speed-bench/expert_cache_sim.py`: LRU 12869 misses, Belady
11088 (every distinct pair once: with foresight the working set fits), the
run itself 15386 (hit rate 0.978). The current policy misses 20% more than
LRU and 39% more than the optimum: 1.5 misses per token out of 5.3. At about
2.4 ms of `sync` per miss that is 3.5 ms of a 57 ms token, so a perfect
policy is worth at most about 6% of decode and an LRU about 4%. Not opened as
a change by this one: it is a candidate (`45-expert-cache-policy`, small,
bitwise by construction) to weigh after `50-ssd-miss-overlap` has changed
what a miss costs.

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
