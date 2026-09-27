# Design

## Context

See proposal.md (Why) and specs/perf-harness/spec.md (requirements). Facts
from the code and from earlier runs that shape the approach:

- **Kernels load from the working directory.** `ds4_gpu_full_source`
  (`ds4_metal.m`) reads `metal/*.metal` at run time relative to the cwd. A
  binary run from the wrong tree silently uses that tree's kernels.
- **The bench lacks the evidence flags.** `ds4_bench.c` has `--ctx-start`,
  `--step-incr`/`--step-mul`, `--show-output` (decoded text only) and
  `--dump-frontier-logits-dir` (prefill only, `%.9g`). `sf-q3-8flash` added
  `--frontiers`, the token-id line and the decode dump in one commit
  (`9f2425f`); the non-MTP half of that diff is what this change ports.
- **The streaming budget arithmetic.** `--ssd-streaming-cache-experts NGB` is
  a total in GiB; the loader takes the prefill headroom (7.12 GiB) first and
  turns the rest into slots of 9.49 MiB (`ds4_streaming_apply_cache_budget`,
  `ds4.c` ~29460). A manual budget is clamped to 7/8 of the recommended
  working set minus the context buffers (`ds4_streaming_manual_cache_safe_bytes`,
  `ds4.c:3751`): at ctx 32768 that is 86 GiB, so `82GB` is admitted and gives
  74.88 GiB of dynamic cache, about 8081 slots. That is above the 7680-slot
  threshold (`DS4_N_LAYER * DS4_N_EXPERT / 2`) in `ds41_prefill_count`
  (`ds4.c:24614`) below which appends under 1024 tokens would be swept
  instead of run token-major. The loader prints one line to read back:
  `ds4: metal SSD streaming cache target T GiB; effective E GiB = 7.12 GiB
  prefill headroom + D GiB dynamic cache (N experts, 9.49 MiB each)`.
- **The prefill policy decides the scenario shapes.** `ds41_prefill_count`
  sweeps multiples of 2048 rows up to the carry cap (8192 rows at ctx 32768,
  read from the +16384 step of the 2026-09-23 sweep, which took two sweeps),
  then a tail: at least 1024 tokens is one more chunk, which is one more full
  layer sweep; under 1024 is token-major through the decode function. So 2500
  is a sweep plus 452 token-major tokens, 3500 is two sweeps, 5000 is a
  4096-row sweep plus 904 token-major, 7500 and 10000 are two sweeps, 16896 is
  two 8192-row sweeps plus 512 token-major.
- **Measured on 2026-09-23** (`tools/speed/out/sf-ds4-1flash-20260923-110221`,
  child before the deep prune, cache target 80 GiB = 72.88 GiB dynamic, 7862
  slots): steady decode 16.4-17.5 tokens/s at every context from 2K to 32K,
  first token 2.2-2.8 s, sweeps of 15.7 s (2048 rows), 17.9 s (+2048 chunk),
  20.5 s (4096 rows) and 24 s (8192 rows); a five-frontier run with 128
  tokens per frontier took 165 s of wall time, so engine open in streaming
  mode costs about 3 s. Upstream at the merge-base ran within 0.6-11.6% of
  the child on decode (the child, running first, was never slower).
- **The parity run of 2026-09-26** (auto cache 69.5 GiB, 7498 slots, 20-token
  prompts, 128 tokens): the CLI's `generation: X t/s` read 11.6-14.9 on the
  child. That figure divides 128 tokens by a time that includes the first
  token's 2.5 s, which alone turns 17 tokens/s steady into about 13. Upstream's
  `077a257` figure, 12.62 -> 13.39, is such a CLI figure. The "about 6 t/s" in
  `AGENTS.md` is not explained by this; Situation 0 measures it.
- **Cache counters have no host getter.** Hits, misses, evictions, bytes read
  and read time are static counters in `ds4_metal.m`, printed only by
  `ds4_gpu_print_memory_report` (`ds4_metal.m:4198`), itself called only at
  cleanup and only when `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY` is set.
  `ds4_gpu.h` exports it, but the bench includes only `ds4.h` and is also
  built for the CPU backend. Hits are counted at lookup time (`peek`,
  `get_protected`), so a readahead that lands before the lookup turns a miss
  into a hit: counts of two identical runs may differ slightly.
- **Routing trace.** `DS4_MOE_RECORD_SELECTED_IDS=path` writes the six selected
  expert ids of every (layer, token) from `ds4_gpu_routed_moe_one_tensor`,
  which `ds41_moe_partial` calls for decode and for token-major prefill. Wide
  sweeps do not pass there.
- **Profilers.** `DS4_METAL_V41_STAGE_PROFILE` prints `ds4: V4.1 stage
  layer=L pos=P rows=R <stage>=<ms>` per layer and stage of a prefill chunk;
  nothing equivalent exists for decode. Decode time is split by
  `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY` (per call: selected read, sync,
  copy, bind; split resident, missing, load, slot, prune, address, wait; load
  prepare, pread, install), `DS4_METAL_CB_TIMES` (driver, queue wait, GPU and
  gap of the first 400 command buffers) and `DS4_METAL_GPU_BUSY_PROFILE`
  (GPU busy accumulated per 64 command buffers).
- **The machine.** MacBook Pro M5 Max, 128 GiB, one internal SSD holding the
  Hugging Face blob; `mactop` 2.1.5 installed; AC power, `powermode 0`. The
  GPU is lightly loaded in streaming mode, so the thermal plateau that shaped
  q3's harness may never be reached here.
- **No upstream commit is adopted.** `docs/upstream-prs.md` does not change.

## Goals / Non-Goals

**Goals:**
- One command that produces a citable A/B verdict, with a confidence interval,
  for changes 30-70, in the streaming configuration the owner runs.
- The harness sees the cache state, so a code change and a cache-state change
  are never confused.
- Bench changes stay small and additive: four sync sites in `ds4_bench.c`, one
  wrapper in `ds4.c`/`ds4.h`, one help line.
- A record of where the plan starts, in absolute numbers and as a ratio
  measured in the same session, opened by the Situation 0 findings.

**Non-Goals:**
- Comparison with upstream inside the harness: StarForge's `parity-check.sh`
  and `speed-compare.sh` are the references against upstream (D12).
- Server, batched-session or concurrency throughput; TP; the CPU backend;
  resident mode (impossible on this machine).
- A GPU section-time mode: `openspec/config.yaml` assigns it to the first
  prefill kernel step that needs it.
- Purging the OS page cache (needs root) or measuring the cold-file case.
- Speed pass/fail thresholds: the harness reports gains and intervals; the
  keep rule in `openspec/config.yaml` reads them.

## Decisions

### D1. Build inputs are trees, and each binary runs from its own tree

`--a DIR --b DIR`. The harness runs `make -C DIR sf-ds4-1flash-bench`, then
runs `DIR/sf-ds4-1flash-bench` with `cwd=DIR`. It records `git -C DIR rev-parse
--short HEAD` and whether `git status --porcelain` is empty. `-m` defaults to
the realpath of the harness's own checkout's `deepseek-v4.1-flash.gguf`, so a
worktree without the symlink opens the same blob.

Alternative: two binary paths. Rejected: a binary does not carry its kernels.

### D2. Bench evidence: port q3's frontiers, ids and decode dump; add `--cache-stats`

- `--frontiers N1,N2,...` (at most 64, strictly increasing) replaces
  `next_frontier`; `ctx_start` and `ctx_max` become its first and last entry,
  so the prompt-length and `--ctx-alloc` checks apply unchanged.
- `--show-output` prints one more line, `ds4-bench: gen[ctx=N] token ids: ...`,
  from the buffer the bench already fills.
- `write_frontier_logits_json` takes a filename suffix; a second call after the
  generation loop and before the restore writes `frontier_%06d.decode.logits.json`.
- `--cache-stats`: after each frontier's row the bench prints
  `ds4-bench: cache report after frontier N` and calls a new
  `ds4_engine_memory_report(engine, label)` in `ds4.c`, a four-line wrapper
  that calls `ds4_gpu_print_memory_report` outside `DS4_NO_GPU` on a non-CPU
  backend and does nothing otherwise. The harness parses the report's
  `streaming expert cache ... hits=H misses=M ... miss_pread=G GiB pread_ms=T`
  line and takes deltas between consecutive reports (the shorter variant of
  that line, without `miss_pread`, appears when nothing was read yet).

Alternative for the counters: a dedicated getter (`ds4_gpu.h`, `ds4_metal.m`,
`ds4.c`, `ds4.h`) and a bench-formatted line. Rejected: four files and a new
format for numbers a report already prints; the extra memory lines in a bench
stderr cost nothing.

### D3. Fixed streaming configuration on every run

Every bench command gets `--ssd-streaming --ssd-streaming-cache-experts 82GB
--ctx-alloc 32768`. 32768 is the owner's default context, keeps the memory
layout identical across kinds (the context buffers, and with them the safe
cache clamp, would otherwise follow each kind's `ctx_max`), and admits 82 GiB.
The harness parses the loader's cache line of every run: the dynamic cache
must lie in 74.5-75.5 GiB and the slot count must be the same in every run of
the invocation, else exit 2 with the line quoted. The summary prints both. If
Situation 0 finds that `82GB` lands outside the window, the constant changes
to the value that lands inside; the spec names the window, not the flag.

Alternative: the auto budget. Rejected: it depends on free host memory at
engine open, so A and B could get different caches.

### D4. Kinds and shapes

| Kind | Bench arguments | What it measures | Predicted | Measured (task 6.2) |
|---|---|---|---|---|
| `decode` | `--frontiers 2048,8192 -n 256` | steady decode at 2K and 8K; the +6144 sweep re-seeds the cache before the 8K decode, as a fresh 8192 prefill would | 75 s | 77-84 s |
| `cold-2500` | `--frontiers 2500 -n 16` | one sweep plus 452 token-major | 44 s | 46-50 s |
| `cold-3500` | `--frontiers 3500 -n 16` | two sweeps | 33 s | 41-45 s |
| `cold-5000` | `--frontiers 5000 -n 16` | a 4096-row sweep plus 904 token-major | 74 s | 75-84 s |
| `cold-7500` | `--frontiers 7500 -n 16` | a 6144-row sweep plus a 1356 chunk | 39 s | 51-54 s |
| `cold-10000` | `--frontiers 10000 -n 16` | an 8192-row sweep plus a 1808 chunk | 42 s | 49-51 s |
| `append` | `--frontiers 5000,5300,6800 -n 16` | +300 token-major and +1500 as one chunk, on a 5000 context | 112 s | 118-123 s |
| `guard-16896` | `--frontiers 16896 -n 16` | two 8192-row sweeps plus 512 token-major | 78 s | 74-76 s |
| `guard-decode` | `--frontiers 8192 -n 2500` | decode over 2500 tokens at 8K | 174 s | 172-173 s |

The predictions used the 2026-09-23 figures (17 tokens/s, sweeps of 16-24 s);
the measured column is the A/A of every kind (task 6.2), 3 s of engine open
included. The 16 generated tokens of the prefill kinds give token ids for
the correctness gate, a decode logits dump and the first-token latency after
each tail kind, at a cost of about 1 s.

The `guard-16896` shape is a wide-sweep shape: `ds41_encoder_acquire` returns
early when the carry cap is set and wide prefill is on, so the encoder
residency path the proposal named is not what this guard runs. It stays the
>10K guard of the typical mix.

Groups: `cold` = the five cold kinds, `guards` = the two guards, `all` = every
kind but the guards. `--kinds` takes names or groups; `--guards` names kinds
that run once, A then B, after the timed quads, and are reported without an
interval. A guard may also be listed under `--kinds`, and then runs quads.
There is no default selection: each change names its kinds.

Alternative: one `cold` kind with the five sizes in one process. Rejected: a
quad would cost about 16 minutes, and a cold prompt after another cold prompt
starts with that prompt's cache state (D5).

### D5. A cold prompt is a fresh process

Each cold kind is one process: the KV is empty, the expert cache holds what
the loader preloads at engine open, the page cache holds whatever the previous
runs left. That state is deterministic and the same for A and B, and its cost
is 3 s of engine open per run. It is not the state of a long-running server,
whose cache holds the previous requests' experts; that state depends on the
content served and cannot be reproduced.

Alternative: `ds4_session_rewind(s, 0)` inside one process. Rejected: rewind
invalidates the checkpoint and the next sync rebuilds from zero anyway, so it
saves only the engine open, while the previous scenario's cache state leaks
into the next and the scenario order starts to matter.

### D6. Schedule and budget

1. Build both trees (D1), preflight (D8), start the GPU monitor.
2. Warm-up: one A and one B run per selected kind, with the logits dumps when
   bitwise. Correctness is checked here; a mismatch exits 1.
3. Preheat (D8): untimed runs of the first kind until `--preheat` seconds
   after the first run started (default 0, at most half the budget).
4. Timed rounds: for each kind in turn a quad A B B A, then the next kind,
   then the next set. Before a quad the harness predicts its duration from
   the latest measured duration of each (build, kind) plus 10%, and starts it
   only if it ends within the budget minus the guards' predicted time.
5. Guards: one A run and one B run per `--guards` kind.
6. Summary.

Budget 1800 s by default, 3600 s at most. Measured: `--kinds
decode,cold-2500,cold-5000 --bitwise` used 1722 s for 26 runs and 10 pairs
(task 6.1); `--kinds all --guards guard-16896,guard-decode --budget 3600`
used 3365 s for 46 runs, one quad set (two pairs per kind) and the two guards
(task 6.2). A change that needs more pairs on one kind selects only that
kind or pools invocations (D10); sweep-only metrics need at least six (D10).

Pairs come only from adjacent runs of the same kind, (A1, B1) and (B2, A2).

### D7. Cache-state check

Per timed run and frontier the harness stores hits, misses, bytes read and
read time (deltas of consecutive cache reports, D2). A pair is dropped, both
runs carrying the reason, when A's and B's hits or misses differ by more than
`--cache-tolerance` (default 0.01 of the frontier's lookups) or the bytes read
differ by more than 5%. `--cache-policy-change` turns the drop into a note:
the change that alters eviction or preload declares it, and then reads the
hit rates the summary prints per kind next to the speeds.

The tolerance exists because hits are counted at lookup and a readahead can
land either side of it. Measured (tasks 3.3 and 6.1): three identical decode
runs and ten A/A pairs gave exactly equal hits, misses and bytes read at
every frontier, so the default 0.01 never drops a pair of identical code and
stays as a guard. The page cache is not purged: warm-up and the A B B A order
balance it, and the bytes-read column shows when they did not.

### D8. Preflight, GPU log, preheat

Preflight as in q3: one `mactop` sample for AC power (or no battery) and
`Nominal`; GPU temperature below `--max-gpu-temp` (60 C); a non-blocking
`flock` on `/tmp/sf-ds4-1flash.lock`; no other process at or above 8 GiB RSS.
Every failure names its condition and exits 2; there is no override.

`mactop --headless --interval 1000 --count 0` logs `gpu.json` for the whole
invocation; fields are looked up by key and a missing key aborts with the
mactop version. A pair is dropped when one of its runs' median active GPU
frequency is below `--min-freq-of-median` (0.90) of the timed runs' median.

The preheat knob stays but defaults to 0. The A/A log (task 6.1, 29 minutes)
shows the thermal state going Heavy within the first two minutes and staying
there, the GPU temperature at 69-72 C after a first spike to 94 C, and the
active GPU frequency fluctuating between 1350 and 1600 MHz with 16-24 W of
power and no trend over the half hour: in streaming mode the GPU waits on
the SSD most of the time, so there is no plateau to wait for, unlike q3's
resident runs. The A B B A order carries the fluctuation, and no pair was
dropped by the 0.90 frequency rule.

### D9. Metrics

- `decode 2048`, `decode 8192`, `guard decode 2500`: `gen_steady_tps` of the
  frontier row (the first token excluded); `first token 2048 ms` and
  `first token 8192 ms` are reported as detail.
- `ttft N` for the cold kinds and the guard: `prefill_tokens / prefill_tps` of
  the row, in seconds: the time from an empty context to the first token's
  logits. `first token ms` of these kinds is detail: the decode step right
  after the tail.
- `append +300`, `append +1500`: the prefill seconds of the second and third
  row of the `append` kind.
- `e2e`: mean over P in {2500, 3500, 5000, 7500, 10000} and N in {200, 1000,
  2000} of `ttft P + N / decode(P)`, `decode(P)` being `decode 2048` for P up
  to 5000 and `decode 8192` above, computed from the A and B medians. A kind
  not run keeps A's value on both sides and the summary names it.

Gains: every ratio is printed so that positive is faster (B/A for tokens/s,
A/B for seconds); the record row and the pooling tool use the same sign.

### D10. Statistics

Per metric: A and B medians over valid pairs, the median gain, and the
bootstrap 95% interval of the median over the invocation's valid pairs
(10000 resamples, fixed seed; none below two pairs). With two pairs the
interval is the range of two values and is not evidence: the all-kinds A/A
read `ttft 3500` at -6.0% (-6.7..-5.3) and `append +1500` at +7.8% with two
pairs each, while ten pairs of `ttft 2500` and `ttft 5000` in the other A/A
sat within ±2.4%. Sweep-only metrics vary 6-8% per pair between identical
builds; a claim on them needs at least six pooled pairs, a decode claim at
2048 about the same, a `decode 8192` or `ttft 5000` claim four. `speed-bench/ab_pool.py
<kind> --metric <name> <out dir>...` pools the pair gains of several
invocations from their `samples.csv` and prints n, the median and the
interval; the keep rule in `openspec/config.yaml` reads that interval. Guards
print the single gain of their pair and no interval.

### D11. Correctness gate

The harness always passes `--show-output`, hashes each frontier's id list
(SHA-256) into `samples.csv`, keeps the lists for the first-difference report,
and compares every run with the first A run of its kind. With `--bitwise` the
warm-up runs also dump logits, validated and compared word by word through
`validate_dump` of `gguf-tools/quality-testing/compare_frontier_logits.py`
(exact fields, canonical `%.9g`, signed zero, argmax consistency), prefill
files before decode files so the first difference says where drift starts.

### D12. Situation 0: three readings before the first measurement

1. `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` on the
   fresh branch, with the loader's auto budget: the largest cache the loader
   admits on its own (76.62 GiB total on this machine), and no manual value
   pushed to the clamp. If it fails, `main` is not a valid reference.
2. `SF_SPEED_FLAGS="--ssd-streaming --ssd-streaming-cache-experts 82GB"
   tools/speed-compare.sh sf-ds4-1flash <gguf>`: child against upstream at the
   merge-base, informational, same sweep as on 2026-09-23. The child runs first
   and colder; a child slower by more than 2% on decode is the `AGENTS.md`
   stop-and-ask case.
3. The 6 / 13.39 / 17 tokens/s question: the CLI (`-n 128` and `-n 1000`, a
   20-token and a 2500-token prompt) and the bench (`gen_first_ms`,
   `gen_steady_tps`) at `82GB`, once more with `--ssd-streaming-cold`. The
   result is a table of conditions per figure at the top of
   `speed-bench/perf-record.md`, and the "around 6 t/s" paragraph of
   `AGENTS.md` is rewritten to the measured shape (a steady rate, a first-token
   cost, and what the CLI's figure includes).

### D13. Baseline decomposition

One diagnostic run per kind, outside the timed runs, with the probes of the
Context section: the timing summary and per-layer stats (miss service per
call, hit rate per layer), `DS4_METAL_CB_TIMES` and `DS4_METAL_GPU_BUSY_PROFILE`
(GPU busy against wall time per token), `DS4_METAL_V41_STAGE_PROFILE` (stage
ms per prefill chunk). The output is one table in `perf-record.md`: for a
decode token at 2K and 8K, and for a 2048-, 4096- and 8192-row sweep, the
share of wall time in miss service, synchronization, GPU compute and the rest.
The start gates of `50-ssd-miss-overlap` and `70-decode-glue-fusions` read
it.

The routing trace: one run of `cold-5000` extended to 2000 generated tokens
with `DS4_MOE_RECORD_SELECTED_IDS` set, which covers the 904 token-major
tokens and the decode. `speed-bench/expert_cache_sim.py` (stdlib) replays the
trace at the configured slot count under LRU and under Belady's optimal
replacement, from an empty cache, and prints both miss counts next to the
measured misses of the same run. Result (perf-record.md): 15386 measured
against 12869 LRU and 11088 optimal over 2904 tokens, worth at most about 6%
of decode; recorded as a candidate change to weigh after `50`, not opened.

The probes also showed that `DS4_METAL_CB_TIMES` waits on every command
buffer and drops decode to 5 tokens/s: it describes a sweep's structure but
never a timed run.

### D14. Performance record

`speed-bench/perf-record.md` opens with the Situation 0 findings (D12, D13),
then the record table in the harness's row format, in segments as in q3:

- Start commit: the `main` commit on which this change lands, the first whose
  bench has `--frontiers` and `--cache-stats`. This change touches no engine
  or kernel code, so that commit's speed is the speed before the plan.
- Start row: an A/A run on a worktree of the start commit, written by the
  first performance change after this one (`30-decode-layer-queue`), with the
  start commit's SHA. Nothing is edited on `main`.
- Later rows: every performance change ends with an A/B against a worktree of
  the segment's start commit and appends the printed row. A sync that changes
  greedy output opens a new segment with a new start row.

### D15. Implementation form

One Python 3 stdlib script, `speed-bench/ab_bench.py` (subprocess, csv,
statistics, fcntl, hashlib, json, re), plus `speed-bench/ab_pool.py` and
`speed-bench/expert_cache_sim.py`. `tests/test_ab_bench.py` (unittest, loads
the script by path) covers the pure parts with synthetic data and is run
directly, not from `make test`, which keeps the Makefile's `test:` block
untouched. Exit status: 0 verdict; 1 correctness failure or a failed run; 2
refused or aborted; 3 inconclusive.

### D16. Prompt

`speed-bench/promessi_sposi.txt` for every kind (1.3 MB, several hundred
thousand tokens; the 2026-09-23 sweep reached 32768 on it). All phases here
are SSD-bound and content only changes the routing, so one prose prompt is
enough; a code prompt is not added.

## Risks / Trade-offs

- [Two pairs per cold size in the default budget is a weak median] → The
  interval says so; a prefill change selects its sizes or raises the budget to
  3600 s; `ab_pool.py` pools invocations.
- [TTFT noise is unknown; the token-major tails may vary with the readahead
  timing] → The A/A run records the per-metric noise floor in the README, and
  the cache columns show whether a noisy pair also read a different volume.
- [`82GB` may land outside the 74.5-75.5 GiB window, or the clamp may change
  with a different free memory] → The window is checked on every run and the
  invocation refuses rather than measures.
- [Identical runs may differ in hit counts by more than the default tolerance]
  → Task 4.3 measures the drift over three identical runs and task 7 sets the
  default from the A/A.
- [The page cache is evicted between runs by other apps] → Preflight refuses
  large residents; the bytes-read column and the 5% rule flag the pair.
- [Predicted durations are off by a factor] → The budget predictor uses
  measured durations after the warm-up; only the defaults in D6 would be wrong,
  and the A/A run corrects them.
- [The 16-token generation of the prefill kinds adds a snapshot or replay] →
  The last frontier of a kind is never restored; only `append` restores, on a
  40-50 MB snapshot, outside both timing windows.
- [Sync conflicts] → `ds4_bench.c`: the option parser, `next_frontier`, the
  `--show-output` block and the post-decode block, all additive; `ds4.c` and
  `ds4.h`: one new function each at the end of the engine accessors; one line
  in `ds4_help.c`.
- [The memory report's line format changes upstream] → The parser requires
  every field it reads by name and aborts with the line quoted when one is
  missing.
- [A later change adds a bench flag the start commit's bench lacks] → A runs
  its own tree's bench, so the harness uses only flags present at the start
  commit; a metric that needs a newer flag is measured against the previous
  step and its record cell stays empty.
- [The decode decomposition has no stage profiler] → The three decode probes
  give miss service, command-buffer gaps and GPU busy time; the remainder is
  reported as "host and other", not invented.

## Migration Plan

Additive only: new bench flags, a four-line engine wrapper, three scripts, a
test, docs and the record. Existing bench invocations and CSV output are
unchanged. Rollback is a revert of the branch.

## Open Questions

- The preheat default (0) and the cache tolerance (0.01) are placeholders
  until the A/A run; the knobs stay whatever the values become.
- Whether `guard-decode` is worth a quad rather than one pair when a decode
  change is small: decided per change by listing it under `--kinds`.
- The default budget after the A/A run, within the 3600 s cap.
