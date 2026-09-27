# Proposal

## Why

Every performance change in this set needs a before/after verdict. It must be
measured on the only machine that counts (M5 Max, 128 GB, internal SSD), where
V4.1 Q2 runs only with `--ssd-streaming`. Nothing in the child gives that
verdict today:

- `sf-q3-8flash`'s `speed-bench/ab_bench.py` fits a resident model. Its 10-minute
  budget, thermal plateau and "warm-up pages the weights in" assume runs of
  6-20 s. Here a decode token takes about 160 ms, and a cold prompt costs one
  or more full SSD sweeps.
- The child's bench has no `--frontiers`, no token ids under `--show-output`
  and no logits dump after decode. There is therefore no token or bit evidence
  for decode changes (checked in `ds4_bench.c`).
- Streaming adds noise sources a resident harness does not see: the expert
  cache state, the OS page cache over the 341 GiB file, and cache-size drift
  when the size is left automatic.
- End-to-end cost follows the prefill policy (`ds41_prefill_count`,
  `ds4.c` ~24610). After the last multiple of 2048, a tail under 1024 tokens
  runs token by token through the decode function, and a longer tail costs
  one more full sweep. A harness that measures only decode t/s and one
  prefill size misses where time goes for 1-10K prompts.
- The baseline is not understood. Upstream `077a257` reports *"warm M5 Max SSD
  decode 12.62 -> 13.39 tokens/s"* on V4.1, and our `AGENTS.md` says about
  6 t/s. Until that gap is explained (conditions or a regression), no step can
  be judged against a meaningful start.

## What Changes

- **Bench additions**, ported from `sf-q3-8flash`'s `20-perf-bench-harness`
  (duplication between children is accepted by design):
  - `--frontiers N1,N2,...`;
  - generated token ids under `--show-output`;
  - a logits dump after each frontier's decode, next to the existing prefill
    dump;
  - a way to time **cold** prompts of several sizes. Either one process per
    size, or a reset to an empty context per frontier; chosen in design.
- **`speed-bench/ab_bench.py`**, ported from `sf-q3-8flash` and adapted to
  streaming:
  - Kept from q3:
    - two build trees, A and B, each run from its own tree with its own
      `metal/`;
    - inherited `DS4_*` variables dropped;
    - q3's preflight: AC power, thermal Nominal, GPU temperature, instance
      lock, no other resident of 8 GiB or more, `mactop`;
    - an untimed warm-up and ABBA quads;
    - a pooled bootstrap 95% CI;
    - the correctness gate: token hashes, bit-exact logits with `--bitwise`;
    - a record row.
  - New for streaming:
    - Both builds get `--ssd-streaming` and a **fixed 75 GiB dynamic expert
      cache**. The harness reads the loader's "dynamic cache" line and refuses
      to run if it does not match.
    - Per run, the expert-cache counters (`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`:
      hits, misses, bytes read, pread time) go into the CSV. For a step that
      does not change cache policy, A's and B's hit and miss counts must match,
      so that the comparison measures code, not cache state.
    - The page cache is not purged (that needs root); warm-up and interleaving
      balance it. Each run records the bytes it read, and a pair whose read
      volume diverges is flagged.
    - Budget: 30 min by default, 60 min at most. It is recalibrated by the
      first A/A run; q3's 10-minute cap was sized for a resident model.
  - **Scenario kinds**, chosen to exercise both prefill tail kinds in the
    owner's typical band:

    | Kind | Scenarios |
    |---|---|
    | `decode` | 256 generated tokens at 2K and 8K of context |
    | `cold` | TTFT of cold prompts of 2.5K (sweep + 452 token-major), 3.5K (2 sweeps), 5K (sweep + 904), 7.5K (2 sweeps), 10K (2 sweeps) |
    | `append` | +300 (token-major) and +1500 (one sweep) on a 5K context |
    | guards | a cold 16K prompt (encoder path, then 512 token-major); decode of 2500 tokens at 8K |

    Each change selects the kinds its target phase needs, plus the guards. The
    summary also prints an **end-to-end estimate for the typical mix**
    (prompts of 1-10K, answers of 200, 1000 and 2000 tokens), computed from
    the measured phases.
- **Situation 0**, before any measurement:
  - `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`,
    with the largest admitted cache, passes on `main`.
  - StarForge's `tools/speed-compare.sh`, which already defaults to
    `--ssd-streaming`, puts the child within ±2% of upstream at the
    merge-base. If the child is slower, stop and ask (the `AGENTS.md` rule).
  - The 6 vs 13.39 t/s gap is explained. Record the conditions (context,
    cache size, page-cache warmth, prompt) under which each figure holds. The
    finding goes at the top of the performance record.
- **Baseline decomposition**, one diagnostic run per scenario, outside the
  timed runs because the probes perturb timing:
  - Probes: `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`, `_LAYER_STATS`,
    `_PREAD_PROFILE`, `DS4_METAL_CB_TIMES`, `DS4_METAL_GPU_BUSY_PROFILE` and
    `DS4_METAL_V41_STAGE_PROFILE`.
  - Output: where a decode token and a sweep spend their time (miss service,
    syncs, GPU compute, host, Engram). The start gates of `50` and `70` read
    this breakdown.
  - One routing trace (`DS4_MOE_RECORD_SELECTED_IDS`) on the typical mix,
    simulated offline for LRU, current and optimal replacement at 75 GiB. If
    the optimum is far better than the current policy, a cache-policy change
    is opened. That change would be bitwise by construction, and no upstream
    PR does it.
- **`speed-bench/perf-record.md`**, with segments as in `sf-q3-8flash`. The start
  row is an A/A run on the `main` commit where this change lands, written by
  the first performance change.

## Capabilities

### New Capabilities
- `perf-harness`: A/B throughput and correctness measurement between two child
  builds under SSD streaming on the M5 Max. It covers the preflight, the fixed
  expert cache, the cache-state checks, the scenario kinds and their
  end-to-end estimate, the budget, the correctness gate and the record row.

### Modified Capabilities
None.

## Impact

- `ds4_bench.c`: frontiers, token ids, decode logits dump, cold-prompt timing.
  These are additive sync sites, the same four q3 recorded. Plus `ds4_help.c`.
- New files: `speed-bench/ab_bench.py`, `tests/test_ab_bench.py` (run
  directly, not from `make test`), `speed-bench/perf-record.md`, and a
  `speed-bench/README.md` section.
- No engine or kernel change. The harness never runs two model processes at
  once.
