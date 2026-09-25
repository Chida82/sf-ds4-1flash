# Upstream PR review notes, 2026-09-25

Working notes behind `proposal.md`. Task 10 builds `docs/upstream-prs.md` from
them. They hold the per-commit analyses of the 69 PRs read in depth, the
facts re-checked in the main session, and the triage method.

- **Base:** upstream main = `0aaea5a` = the child's merge-base. Upstream had
  no newer commit on the review day.
- **Target:** Apple M5 Max 128 GB, internal SSD, `DeepSeek-V4.1-Flash-Q2.gguf`
  (340.6 GiB: about 152 GiB of main weights and 189 GiB of Engram tables).
  - Routed gate/up are IQ2_XXS and down is Q2_K, about 9.5 MiB per expert
    slot.
  - Attention projections, shared expert and output are Q8_0; `hc_*`, the
    indexer and `token_embd` are F16; Engram is I8/F16.
- **Regime:** `--ssd-streaming` only, with a fixed 75 GiB dynamic expert cache
  (about 8090 slots, roughly 53% of the 142 GiB of routed experts). Decode runs
  at about 6 t/s, roughly 160 ms per token.
- **Rules:** see the `context` block in `proposal.md`. In short: no output
  change, measurable on this machine or `history`, end-to-end focus, at least
  +1.5% above 800 runtime lines, never DSpark.

The six analyses were done read-only by subagents, from diffs and code, with
nothing built or run. Their effect figures are **estimates**. Items marked
*verified* were re-checked in the main session.

## 1. Method and funnel

The PR heads were fetched into a scratch bare clone (`--reference` to the
StarForge upstream mirror), with `+refs/pull/*/head:refs/pull/*`.

| Stage | PRs | How |
|---|---|---|
| PR refs | 708 | `git for-each-ref refs/pull` |
| unmerged | 669 | 440 open (`gh pr list --state open`) + 229 closed without merge (REST `pulls?state=closed`, `merged_at == null`) |
| patches not in main | 664 | `git rev-list --count main..refs/pull/N` > 0, then `git cherry main refs/pull/N`: at least one `+` |
| touch engine/Metal files | 307 | the diff touches `ds4.c`, `ds4_metal.m`, `metal/*`, `ds4_engram.[ch]`, `ds4_deepseek41_gpu.h` or `ds4_gpu.h` |
| not other-model dominated | 211 | GLM+Qwen+CUDA hits ≤ 4 × (V4.1+Engram+SSD hits + 2); see `triage-candidates-2026-09-25.md` |
| read commit by commit | 69 | chosen by hand from the 211; the rest are server, agent, tokenizer, steering, DSpark/MTP, CUDA/ROCm, other models, CPU/x86, Vulkan |

**Reachability oracle.** For each hunk in the engine files, the enclosing
function name from `git diff -U0` is looked up among the identifiers of the
pruned child. A hunk in a function the child no longer has is almost surely
unreachable for V4.1, since the prune removed only what V4.1 does not reach.
Call sites were read wherever it mattered.

Dates: V4.1 Metal support landed in `bd66c40` (2026-09-12) and SSD streaming
in `9ba160a` (2026-06-04).

## 2. Facts re-checked in the main session (verified)

- In streaming, V4.1 decode runs routed MoE through
  `ds4_gpu_routed_moe_one_tensor` (`ds4_metal.m:32366`). That is the generic
  `stream_expert_cache` V4 Flash used, so generic streaming PRs can apply.
  The IQ2_XXS/Q2_K single-token path `use_iq2_selected_slots`
  (`ds4_metal.m:33026`) requires `g_ssd_streaming_mode`.
- `ds41_graph_step` (`ds4.c:24502`) ends and waits on the command buffer after
  every layer on one box. Only `tp_world == 2` queues layers.
- The Engram is read in parallel. `ds4_engram.c:187-257` uses
  `ENGRAM_READERS = 16` through `dispatch_apply_f`, from upstream
  `6c00e2d` + `077a257`. An earlier claim that it was serial was wrong: the
  check looked for `pthread_create` only.
- Upstream `077a257` (2026-09-18) says: *"Warm M5 Max SSD decode improved from
  12.62 to 13.39 tokens/s with byte-identical output"*. Our `AGENTS.md` says
  about 6 t/s. This gap is unexplained; `20` must explain it.
- Prefill policy, `ds41_prefill_count` (`ds4.c:24610`) with its caller at
  `ds4.c:32227`:
  - `minimum` is 256, raised to 1024 when streaming, `pos > 0` and the
    configured cache holds at least `DS4_N_LAYER * DS4_N_EXPERT / 2 = 7680`
    slots;
  - a remaining count of 4096 or more gives a wide sweep of
    `min(remaining, carry_cap)`, rounded down to a multiple of 2048;
  - otherwise the chunk is `min(remaining, 2048)`;
  - a remaining count below `minimum` goes token by token through
    `ds41_graph_step(..., NULL)`;
  - prompts of 16K or more take the encoder-resident path
    (`count = remaining - 512`), then 512 token-major steps.
- Cache flag semantics (`ds4.c:29438-29540`): `--ssd-streaming-cache-experts NGB`
  is a GiB *total*; prefill headroom (about 7.12 GiB) is taken first. The
  auto run showed 82.62 GiB total = 7.12 + 75.50 dynamic. So 75 GiB dynamic
  is a flag of about `82GB`.
- Deep-prune bug at `ds4.c:24087`: `(shared_here && !false && gate) || up ||
  swiglu || bf16 || down`, where upstream has `shared_here && !shared_queued &&
  (...)`. The other two `!false &&` sites (`ds4.c:17161`, `ds4.c:17625`) are
  harmless `&&` chains.
- `ds4_gpu_glm_stream_selected_prefetch_take` (`ds4_metal.m:16091`, called at
  `:33493`) has no producer in the child.
  `ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor` exists in main,
  called only from GLM code (`ds4.c` 49046, 51621, 56994, 66401, 66706).
- The measurement switches exist in the child: `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`,
  `_LAYER_STATS`, `_PREAD_PROFILE`, `_PREAD_THREADS`,
  `DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD`, `_SLABS`, `_SLAB_MB`,
  `DS4_METAL_CB_TIMES`, `DS4_METAL_GPU_BUSY_PROFILE`, `DS4_METAL_V41_STAGE_PROFILE`,
  `DS4_METAL_ENCODER_TIMELINE`, `DS4_MOE_RECORD_SELECTED_IDS`.
  - StarForge `tools/speed-compare.sh` compares the child against upstream
    and defaults to `--ssd-streaming`.
  - The child's bench has `--dump-frontier-logits-dir`, `--show-output` and
    `--teacher-forced-decode`, but no `--frontiers`.

### Runtime size of the candidate commits (`git show --shortstat`, tests included where the commit has them)

| Commit | PR | Lines |
|---|---|---|
| `bd6f912` | #1041 | +16 −2 |
| `fdbf7f2` | #1041 | +26 −6 |
| `9b50495` | #1034 | +192 −5 (7 files, mostly test and bench) |
| `2a281b08` | #1073 | +36 −13 |
| `29ce2717` | #1073 | +1 |
| `d95f8b61` | #1073 | +403 −57 |
| `edceb7ab` | #1073 | +115 −1 |
| `e7683961` | #1073 | +5 −4 |
| `4fbbc4a4` | #1073 | +31 −12 |
| `d8d1523b` | #1073 | +4093 −387 (includes DSpark) |
| `1923131d` | #1073 | +62 −3 |
| `10118742` | #1073 | −3 |
| `3b7f8f22` | #1073 | +110 −9 |
| `ce5a812f` | #1073 | +199 −32 |
| `ccbf2c08` | #1073 | +3 −1 |
| `64240fb9` | #1073 | +5 −18 |
| `798c64f4` | #1073 | +21 −5 |
| `a2e2ea53` | #952 | +164 −2 |
| `a3043bb2` | #952 | +314 −11 |
| `bac91c21` | #952 | +576 −8 |
| `c12d639a` | #952 | +273 −9 |
| `8f5a7458` | #621 | +96 −1 |
| `f7695ea0` | #621 | +51 −2 |
| `a1afb82e` | #570 | +61 |
| `66ca6ef7` | #570 | +15 |
| `66f757b6` | #1033 | +656 (53 in `ds4_metal.m`) |
| `60051d46` | #849 | +796 −10 |
| `e154aa8b` | #758 | +462 −25 (only the rb16 hunk is taken) |
| `482e246a` | #864 | +345 −49 (only the LUT is taken) |
| `4b9ff600` | #959 | +150 −64 |
| `e8c84dda` | #959 | +198 −1 (test) |
| `be6a8ce4` | #1060 | +510 |
| `6856a23a` | #1061 | +283 −6 |
| `f6639cfd` | #1089 | +548 −23 |
| — | #1042 total | +1642 −37 (6 files) |

## 3. Decode scheduling and profiling: #1041, #1034, #1067, #1049, #828, #852, #743

| PR | State | Head | Verdict | Reason | Effect (decode / prefill) |
|---|---|---|---|---|---|
| #1041 | open | `fdbf7f27` | `bd6f912` adopt (2 scope fixes); `fdbf7f2` open → history | The only queue that is default-on and reachable in SSD streaming; bitwise logits on M2 Ultra Q2 SSD | medium, about +4-8%: 38 of about 81 commit+wait round trips per token removed, and layer L's MoE tail runs while L+1 encodes / none |
| #1034 | open | `0a21d1ab` | code superseded by `bd6f912`; test and bench flag adopt | Same queue, but opt-in, streaming-only, no flush | medium−, +3-6% (queue only) / none |
| #1067 | open | `dceba87e` | not reachable in target mode; `d1738d2` idea | c1-c3 and c5 require `!g->streaming`; c4 is pre-M5 only | none as shipped; ideas ≤1-2% |
| #1049 | closed | `0c5fa642` | drop | closed by the author at +0.79%; requires `!g->streaming` | none |
| #828 | open | `3add8f96` | open | diagnostic, off by default | none |
| #852 | open | `e01e2156` | next sync | TP multi-session watchdog fix; the patch is 296 commits behind main | none on one box |
| #743 | closed | `0dcbfbc6` | superseded by `1a976b7d` | main's default TP poll gates | none |

None of these changes arithmetic, and all claim bitwise or byte-identical
output.

**#1041.** Measured on M3 Ultra 512 GB, Q4, resident: 17.1 → 21.7 t/s with the
queue, 23.1 with the flush, byte-identical. Re-measured by Dango233 on M2 Ultra
192 GB, Q2, SSD, slabs disabled: 10.64 → 12.08 t/s (+13.5%, about −11 ms per
token). His 512-step harness matched 68,389,120 logit floats exactly, and the
forced-eviction test passed.

- **`bd6f912` (adopt).** It extends main's TP-only `queue_layers` (from
  `bd66c40`) to one box and calls `ds4_gpu_flush_commands()` after every
  non-drain layer.
  - On by default, no device gate. Rollbacks:
    `DS4_METAL_DISABLE_V41_DECODE_QUEUE` and `DS4_METAL_DISABLE_V41_DECODE_FLUSH`.
  - Reachable: every single-stream SSD decode, including the server's, because
    `ds41_sessions_batch_supported` refuses streaming sessions.
  - No removed code is involved (`g->imatrix` is already gone). The only
    conflict: the PR base calls `ds4_engram_read`, where main calls
    `ds4_engram_read_batch`.
  - **Bug, still present at `fdbf7f2`:** `queue_layers` does not exclude
    `layer_resident` (quality + streaming). At layer 1 `ds4_gpu_begin_commands()`
    returns 0 while the batch is open (`if (g_batch_cb) return 0`), so
    `--quality --ssd-streaming` decode fails. Add `!layer_resident`, as #1034's
    `!g->quality` does.
  - **Scope fix:** the flush also fires on `tp_world == 2` and changes TP buffer
    packaging, which poll gates and `DS4_TP_POLL_MAX_INFLIGHT` already manage.
    Limit it to `tp_world == 1` unless it is measured on the pair.
- **`fdbf7f2`** queues resident decode through the logits tail. `whole_token`
  requires `!g->streaming`, so in SSD mode the schedule is exactly `bd6f912`'s.
  It was +1.4% resident on M3 Ultra and cannot be measured here.

**#1034.** M2 Ultra, Q2, SSD, slabs disabled: 10.17 → 11.32 t/s (+11.3%),
bitwise in a same-engine harness. Profile: 81 → 43 command buffers per token,
75.3 → 66.8 ms per token, GPU time 41.4 ms in both.

- **`9b50495`.** The code is the same queue without the flush, opt-in through
  `DS4_METAL_ENABLE_V41_STREAM_DECODE_QUEUE`: superseded.
  - **Adopt** `check_stream_decode_queue` in `tests/test_deepseek41_graph.c`.
    Two sessions share a 512-expert cache, which forces eviction; logits,
    Engram history and state spans are compared bitwise at positions 121-144.
  - **Adopt** the 4-line `--ssd-streaming` flag in
    `speed-bench/metal_decode_schedule_bench.c`. Both files exist in the child.
    Retarget them to #1041's environment names, and add a cache-size
    pass-through.
- `7a18d09` (`__APPLE__` guard merge) is not needed. `0a21d1a` (reports) is dropped.

**#1067.** M3 Ultra 512 GB, Q4, resident: 17.9 → 26.1 t/s, identical output.

- `6f7319c` (flush every N layers) is not reachable: `ds41_decode_queue_enabled`
  requires `!streaming` and a pre-M5 chip. Its separate Engram buffer per table
  removes only the layer-13 drain, which costs about one wait in streaming.
- `fd6dca4` (Engram reader threads): the concurrency is already in main
  (`6c00e2d5` + `077a2576`: 16 dispatch readers from 8 rows up). What is left,
  both tables at once overlapped with the layer-0 encode, is worth ≤0.5 ms per
  token. Its original join at the first flush is unsafe; `dceba87` fixes that.
- `d1738d2` (allocation-free plain pipeline getter) is an idea. The cache
  exists in the child (`ds4_gpu_set_decode_pipeline_fast_lookup`), but only
  the mul_mv getters use it, and only the generic `metal_graph` decode arms it.
  In streaming, the CPU encode after each readback is on the critical path: M3
  Ultra measured 4.0 → 0.7 ms per token of encode. Measure encode time first
  with `DS4_METAL_CB_TIMES`.
- `2f59c4e` (small copies as a compute kernel) is dropped: pre-M5 only and
  measured neutral. It also pushes int and bf16 payloads through the f32 copy
  kernel; bitwise identity is claimed, not verified.
- `dceba87` (batched decode) is not reachable: streaming sessions are never
  batched.

**#1049.** `0c5fa64` (reuse gathered KV) is dropped: flat alone, +0.79% on top of
#1041, resident only.

**#828.** V4.1 numbers: M3 Ultra, Q4, resident, 36.9 ms busy in a 37.7 ms span
when queued, against 46.9 ms with the drains.

- `3f20d5e` (Metal `ds4_gpu_stage_flush`/`report`) is open. Its `metal_graph_*`
  hooks reach only the layer-slice path, and its CUDA stub targets removed code.
- `3add8f9` (V4.1 decode stage tags) is open.
  - Caveat in SSD mode: buffers committed inside the routed MoE (the id
    readback, the hits-first flush) are not tagged. Resident-expert GPU time
    therefore goes missing and the gap looks bigger than it is. Tag every
    committed buffer while the probe is on.
  - It adds about 15 commits per layer when on, so it measures a different
    schedule.
- Main already has `DS4_METAL_ENCODER_TIMELINE`, `DS4_METAL_CB_TIMES`,
  `DS4_METAL_GPU_BUSY_PROFILE` and `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`.

**#852.** `e01e215` is next sync. On a two-Mac M5 Max TP pair: bitwise tokens,
and forcing the split costs about 15% of prefill. It applies to the child:
under server session batching, `event_arrival` makes V4.1 TP gates use
`encodeWaitForEvent`, since poll gates are off in batch mode and in SSD mode.
It predates V4.1 and the poll gates: do not hand-port it.

**#743.** `0dcbfbc` is superseded by `1a976b7d`, main's default bounded GPU poll
release. Its claim was +23% on two M3 Ultras on V4 Flash, relying on the
undocumented `coherent(system)`. `DS4_TP_NO_KEEPALIVE=1` already exists, so it
is a measurement for the pair only.

**Choice.** #1041, #1034 and #1067 all remove the same per-layer
`ds4_gpu_end_commands()`. Take `bd6f912`'s mechanism (the queue plus a
non-blocking commit per layer), add #1034's scope guard, and gate on #1034's
forced-eviction test.

In SSD mode the routed MoE already commits and waits every layer to read back
the six expert ids (`use_iq2_selected_slots` → `end_commands` + `tensor_read`).
The queue therefore cuts about 81 waits to about 43. The flush lets layer L's
MoE tail run while L+1 encodes, which is why #1041 beat #1034 on the same M2
host (+15.6% vs +10.7% in the harness). #1067's flush every 4 layers makes no
difference in streaming.

Ordering constraints:
- the queue is off whenever `layer_resident` is true;
- the layer-13 drain stays until the second Engram table has its own buffer;
- any Engram reader thread is joined before layer 1 is encoded;
- the flush comes after the drain decision and is skipped on drain layers.

What stays synchronous per token:
- 40 id readbacks;
- the miss preads (68-75 GiB of slots against the 142 GiB pool);
- the hits-first split waits;
- the drains at layers 13 and 39, and the logits wait;
- the Engram reads.

Miss service dominates, so expect about 8-11 ms per token saved, not M2's
13.5%.

**Measurements needed.**
- The A/B uses:
  - `DS4_METAL_DISABLE_V41_DECODE_QUEUE=1`: queue off (baseline);
  - the default: queue and flush on;
  - `DS4_METAL_DISABLE_V41_DECODE_FLUSH=1`: queue on, flush off.
- Upstream measured with slabs disabled in both arms. The child ships with
  slabs on, so measure the flush at that default; a per-commit cost could
  erase what it gains.
- Cache hits, misses and evictions must be equal between the arms.
- `--quality --ssd-streaming` must still decode.
- Keep the flush off for TP.

## 4. #1073 "Speed up DeepSeek V4.1 Flash on Metal"

State: open and mergeable. Head analysed: `3d3c83bb`, which merges `0aaea5a`
into a branch cut at `8db1d1d1`. It has 54 non-merge commits:

| Class | Commits |
|---|---|
| single-box V4.1 Metal | 18 |
| DSpark | 9 |
| TP | 9 |
| cleanup, CUDA and tests | 10 |
| quantizer | 3 |
| MXFP4/Q4_K-gated | 3 |
| server | 1 |
| docs | 1 |

Claims (M3 Ultra 512 GB, resident): Q2 generation 19.8 → 36.2 t/s at 2K, and
prefill 339 → 389 t/s; evals byte-identical to main. The PR does not touch the
SSD-streaming expert path: `routed_moe_one`'s streaming branch, the stream
cache, the hits-first split and the per-layer id readback all stay.

| Commit | Subject | Verdict | Reason | Effect |
|---|---|---|---|---|
| `2a281b08` | Queue V4.1 decode layers on a single node | adopt with `29ce2717` (variant) | Flushes after L0 and every second layer. `engram_rows_b` removes the layer-13 drain (TP keeps it). In streaming `routed_moe_one` still ends the buffer for the ids. Only buffer boundaries change | low (1-3%); try `DS4_METAL_V41_DECODE_FLUSH_LAYERS=1` |
| `d95f8b61` | Round activations inside the producing kernels | adopt | bf16 rounding folded into the Q8_0 matvec (plain kernel only), RMS norm, HC sum/expand and rope. Same templates, identical bf16 helper | low (about 8 dispatches per layer) |
| `edceb7ab` | Select experts in one dispatch | adopt, verify | `kernel_dsv41_router_one`. The head version has main's `0719a0ba` softplus. Claims the same bitonic order and normalisation. Kill switch `DS4_METAL_DISABLE_V41_ROUTER_ONE` | low |
| `e7683961` | Skip candidate selection while every block is kept | adopt | Up to 2048 blocks (pos ≤ 16K on index layers ≥20), top-k selects all and the filter is the identity: exact | low |
| `d8d1523b` | Speed up V4.1 decode + DSpark verify | port the non-DSpark subset by hand | see below | medium (5-9% decode estimated; Engram part <1%) |
| `4fbbc4a4` | Encode the vocab head before the last drain | adopt the head part | One buffer round trip less per token; skips the empty publish loop on non-source prefill layers. Its short-sweep half was reverted (`64240fb9`) and redone (`798c64f4`) | low |
| `1923131d` | Match rope contraction of the fused rope-quantize store | take with `d8d1523b` | Explicit `fma` matching `kernel_dsv41_rope`'s contraction; compiler dependent; bitwise unit test | correctness |
| `29ce2717` | V4.1 prefill rows get their own second Engram table | take with `2a281b08` | fixes the fallback when `DS4_METAL_DISABLE_V41_BATCH_HC` is set | none |
| `10118742` | Publish ratio-1 keys in batches on Metal | adopt after tests | layer-20 key publication in prefill batched through the exact-rows F16 projection | prefill low-medium |
| `3b7f8f22` + `ce5a812f` | select-all ≤512 visible keys; batched candidate blocks | adopt after tests | unit tests exact; `ce5a812f` only above 16K | prefill low |
| `ccbf2c08` + `64240fb9` + `798c64f4` | decoder suffix from 2541; short sweep | **output-changing in one case** | see the prefill note | high for cold 3-8K prompts |
| `4b1b1519` | score index keys, one thread per key | drop: output | a different reduction; top-2048 can flip at near-ties; default on at ≥8192 keys | medium at ≥8K, changes output |
| `af7c02b5` | radix top-k select | drop: output | at ≥16384 keys; tied keys by ascending id; many scores tie at 0 after ReLU | medium at ≥16K, changes output |
| `262b4a66`, `a6b50ff6` | simdgroup-matrix rows kernels | drop: output | "round a few outputs differently"; reach `decode_rows_exact`, shared-expert rows and attention-low rows for 3-8 rows; built for DSpark verify | none single-session |
| `7da9535f` | idle server slots sync in the engine's prefill chunk | drop: output | only `--batched-sessions` (off by default); 2048 → 8192 quanta, 4× fewer sweeps; chunking numerics change | high but only in batched server mode |

**`d8d1523b` without DSpark.** With Q2, every single-row fusion is reachable:
Q8_0 attention and shared expert, F16 HC and indexer, F32 router, and the
M3/M5 device gate passes on M5 Max.

- HC block input in one dispatch, twice per layer.
- q_a and kv Q8 matvecs paired, and their norms paired.
- q_b with rope.
- rope + quantize + store.
- Staged attention that gathers by id itself (no `gather_kv` copy).
- Attention low with inverse rope.
- Attention output and shared down fused into the HC expand.
- Shared gate/up SwiGLU.

About 59 → 17 dispatches per decoder layer. Engram start/finish reads both
tables asynchronously, overlapped with layers 0 and 13. Not applicable: the
DSpark code, the MXFP4 MoE kernels, the TP verify block and the 2-8-row
kernels.

**Prefill note.** For 3072-8191 tokens, the PR runs one wide sweep when the
tail (`count % 2048`) is 0 or at least `minimum` (256 when cold). Main, with
at least 7680 slots, runs a second full sweep for tails of 1024 or more, and a
token-major tail below that. The PR matches main's resident schedule (same
partitions). It is **not** bitwise in the token-major-tail case, where batched
kernels replace the decode kernels.

**The rest.**
- DSpark (9: `a60edc61`, `c674b198`, `1e3bcf8d`, `bd85ba6a`, `b7bcccde`,
  `1c692066`, `fd709191`, `258ad331`, `66dff869`): not applicable, never.
  `66dff869` matters only for reaching the head state of `d8d1523b`.
- TP (9):
  - `9f3892d2`, `a13b513e`, `867465cc`, `c9bfdcc9`, `83876259`, `4fe6a780`:
    history (TP pair);
  - `8d73a0ef`: drop. It turns off `tp_shard`, so both ranks map all 384
    experts; that breaks the 2×128 GB layout (about 81 GiB per rank) and
    changes TP sums;
  - `dc81436d`: not reachable (Q4/MXFP4 fallback);
  - `5c2dac7e`: next sync (a log newline).
- Quant-gated: `d744ebb9` and `5432223d` are Q4_K tiles, pre-M5, resident;
  `e49643ff` is MXFP4 concurrent shared expert, resident. All history.
- Quantizer (`c016ea77`, `0b2d6e28`, `b3d4a267`): not applicable. Docs
  (`aea1a0ba`): drop.
- Cleanup and tests:
  - `0ac42d6f`, `8be10050`, `a15028ee`, `c4b66b90` are refactors to the final
    shape; take them with a port;
  - `a3f6f313`, `c6f4086f`, `7d89c59c` are tests; take them;
  - `ed43e1a5`, `2a551936`, `92197579` are CUDA. `92197579` confirms that
    multi-row batch attention is not decode-exact.

**Risks.**
- Bitwise on M5 / macOS 27 is unproven: only M3 Ultra was measured.
  - The fused ropes rely on compiler contraction.
  - Attention-low uses `precise::sincos`, where `kernel_dsv41_rope` uses
    `precise::sin` and `precise::cos`.
  - The HC block input replicates reductions with arrival counters.
  - Only rope-quantize has a bitwise unit test.
- Streaming is untested upstream. The `--decode-switch` harness (`a3f6f313`)
  supports streaming, but its `main()` runs resident only. Run it with
  `--ssd-streaming` for DECODE_QUEUE, QUEUED_HEAD, HC_BLOCK_INPUT,
  EXPAND_FUSION, ROUTER_ONE, ROPE_QUANTIZE and GATHERED_KV_STAGE; each run
  checks 65 steps for bitwise logits, history and KV.
- Disable or omit the output-changing defaults:
  `DS4_METAL_DISABLE_V41_INDEX_SCORE_WIDE`, `DS4_METAL_DISABLE_V41_TOPK_SELECT`,
  `DS4_METAL_DISABLE_V41_ROWS_MMA`, and the short sweep in streaming.
- Porting `d8d1523b` means a manual port of the head state, and a large
  permanent conflict surface in `ds41_*` and `ds4_metal.m`.

## 5. Fusions: #1042 against #1090

**#1042.** Open. Head `6e92e920`, 7 commits, base `6e4c285a` (75 commits behind
`0aaea5a`).

- It merges onto `0aaea5a` with no textual conflict. On the child it conflicts
  twice in `ds4.c`: the shared-expert block of `ds41_moe_partial`, where the
  child's own fold is wrong (section 2), and the CUDA `ds41_decode_island`,
  which stays deleted. Plus two trivial `__APPLE__` test hunks.
- Every helper it calls still exists in the child.
- Gates: `tp_world == 1`, the rollback environment variables, and type checks
  (F32 router, Q8_0 shared expert). There is no streaming, quality or device
  gate: every fusion runs under `--ssd-streaming`.

**Not exact against `0aaea5a` as submitted:**
1. Stale softplus. `kernel_dsv41_router_select` computes `log(1+exp(x))`, while
   main's `0719a0ba` uses a log1p series below exp(x) < 1/32 → logits below
   about −3.47 differ. Its `--moe-fuse` test (logit σ ≈ 6) should fail on the
   child, which makes it a good oracle.
2. Tie order. The fused select is canonical (score descending, index
   ascending), from `kernel_argsort_f32_i32_desc_canon`, which exists only in
   #832. The child uses the plain bitonic sort, which leaves ties unordered.
   `6e92e920` relaxes the test to hide this. Exact ties can reorder experts,
   and a tie at the 6th/7th boundary can change the selected set.
3. Fast-math. The router clamps against a compile-time `INFINITY`, and the
   collapse's straight-line `0.0f + x*p` can produce a signed-zero mismatch on
   zero residual rows. #1090 hit this; the tests have no zero/NaN/Inf/denormal
   rounds.

**M5 is untested** (only M4 Pro and M3 Ultra were measured).
- The single-dispatch router `d6a34d62` uses the last-arriving-threadgroup
  pattern that was nondeterministic on M3 Ultra.
- HC norm+mix uses `_cluster2` at n = 20480.
- The F16 BF16-store kernel lacks the nr0=1 case that M5 uses.
- When a pipeline is missing, the code fails instead of falling back.

| Commit | Subject | Verdict | Reason | Streaming-Q2 effect |
|---|---|---|---|---|
| `b43fcce6` | HC glue 19→6 | adopt after M5 test | norm+mix gate widened to 20480; memcmp tests; needs zero/−0 rounds | low-medium: about 13 dispatches + 1 blit per layer (about 1-2.5%) |
| `c1bd5315` | MoE glue (router+select, shared, tail) | shared adopt; router open (fix); tail superseded by `f61a83d7` | stale softplus, #832-dependent ties | low (about 1-2%) |
| `d6a34d62` | single-dispatch router, M5 only | open | default on the target, never run on M5 | tiny |
| `5b8b6ac3` | separate rollback switches | adopt | needed for A/B | none |
| `bc628554` | expand4 folds routed+shared sum | superseded by `f61a83d7` | — | — |
| `f61a83d7` | attention glue; shared down before routed | adopt | BF16 on store for Q8_0/F16; q/kv norm + KV RoPE + FP8 + window store 6→1; heads BF16 + inverse RoPE 2→1; logits collapse 4→1 | low (about 0.5-1.5%) |
| `6e92e920` | relax the tie test | drop | hides the tie divergence | none |

Transfer: about 41 dispatches and 2 blits fewer per layer, i.e. about 1,650
dispatches and 80 blits per token. On the author's resident M3 Ultra, on top of
#1041, GPU busy time fell by 5.7 ms per token (HC 2.1, router 1.55,
shared+tail 1.0, attention 1.0). Here that glue runs in series with the SSD
reads, so the estimate is about 5-10 ms of a 165 ms token: **+3-6%**.

**#1090.** Open. Head `849e039b`, 6 commits, based on `0aaea5a`; +24,565/−401
lines in 190 files. Every V4.1 path requires:
- `strcmp(device, "Apple M3 Ultra") == 0`;
- `!g_ssd_streaming_mode`, `!g_quality_mode` and TP world 1;
- for the queue, pipeline and tail-cull paths, Q4_K experts in every layer
  and a text-only session.

Its Q8 BF16 store also refuses when `ds4_gpu_mpp_available()` is true, which is
the default on M5. It is inert on this machine.

| Commit | Subject | Verdict |
|---|---|---|
| `06ba1c57` | GLM HC/KDA/sparse attention | not reachable (also adds encoder counters and tuning gates the V4.1 commits reference) |
| `3cba8f06` | GLM BF16 requant tool | not reachable |
| `34794be8` | GLM routing, tool checkpoints | not reachable (GLM); its server KV tool-map rewrite is open, review separately |
| `d9758788` | V4.1 fusions | router: **idea** (select-only, 512 threads, replicates the bitonic network exactly, including padding and unordered ties, with the current softplus: the fix for #1042); HC norm/shared: superseded by #1042; histogram top-k: drop (needs GLM kernels); Q4 tail cull: not reachable; M3U queue: superseded |
| `d3d6f6cb` | V4.1 pipeline, Engram step reads, compute copies, Q8 BF16 store, hardening | pipeline: not reachable; compute copy: idea; Q8 store: superseded; hardening: take into a #1042 port; Engram overlap: negligible |
| `849e039b` | docs/evidence | drop |

- **Overlap.** The router is exact in #1090 and not in #1042. #1090's HC is a
  subset of #1042's. The shared expert has the same arithmetic. Both define
  `kernel_dsv41_mul_mv_q8_0_f32_bf16`, in different files, which is a
  duplicate symbol in the concatenated library.
- **#1090's V4.1 parts need its GLM commits.** The top-k extends GLM plumbing,
  `BF16_STORE` extends `COHERENT_STORE`, and the host profile uses the GLM
  counters. A simulated pick onto the child gives 8 content conflicts and 4
  modify/delete conflicts. Router, HC, shared and copy can be extracted by hand
  (about 250 lines); top-k cannot.
- **A #1042 port, if ever chosen:** replace its router with #1090's
  `kernel_dsv41_router`, and take #1090's hardening. That means runtime clamp
  and width arguments, a zero-safe collapse, fallback instead of failure, and
  the edge-value tests. Cost: about 1.79K lines in 6 files, plus 80-120 lines
  of fixes. Oracles: `tests/test_deepseek41_metal --hc-fuse --moe-fuse
  --attn-fuse`, reached through `make test-deepseek41-metal`, not `make test`.
- **Owner decision (2026-09-25):** one PR per code zone. The glue zone goes to
  #1073's line; #1042 and #1090 are history.

## 6. V4.1 kernels, indexer and fixes

| PR | State | Head | Verdict | Reason | Effect |
|---|---|---|---|---|---|
| #1043 | open | `0e48ed8` | not reachable → history (Q4, resident) | the group-6 table needs Q4_K gate+down and `!g_ssd_streaming_mode` (`ds4_metal.m:32805-32820`) | none |
| #1124 | open | `e0b2093` | not reachable | V4 Flash fused norm/RoPE/FP8, called only from `metal_graph_encode_decode_layer_phase` (`ds4.c:16442`); V4.1's `kernel_dsv41_quantize` already uses `simd_max` (`dsv41.metal:72`) | none |
| #1061 | open | `6856a23` | drop: output (idea: bitwise rewrite) | MMA decode scorer at n_comp ≥ 1024 (the code says 1024, the body 4096); different f32 summation order | low ≤32K, medium ≥128K |
| #1060 | open | `be6a8ce` | drop: output (owner rule) | radix-select top-k for rows ≥4096 wide; measured on this exact target; differs on bit-equal scores | low ≤32K, medium ≥128K |
| #959 | open | `b4605a0` | history (≥128K) | bit-exact pruning of the non-causal merge cascade V4.1 decode uses | about 0.1 ms/token at 32K, about 1 ms at 128K |
| #832 | open | `eb2e545` | drop | scorer unreachable; its canonical comparator reaches V4.1 and breaks the tie invariant; stream512 unreachable | none (negative) |
| #831 | open | `f7ad40c` | not reachable | V4 Flash pre-M5 tiled scorer | none |
| #830 | open | `55b7103` | superseded by #831 | its only commit is #831's first | none |
| #782 | open | `d5c8fd0` | not reachable; idea → #1061 | V4 Flash 64-head scorers; prefill measured not exact | none |
| #758 | open | `e154aa8` | adopt the rb16 hunk only (hand port) | V4.1 prefill dispatches `heads16_dual`; rb16 is bitwise; fused512 unreachable | low, prefill only, n_comp ≥ 512 |
| #169 | closed | `41cf971` | drop (in main, modified) | M5 support landed differently; its decode top-k 512→8 changes output | none |
| #399 | open | `1327f3a` | drop | only 2-8-token prefill chunks, not bitwise; multi-session batch refused under streaming (`ds4.c:32650`) | none |
| #1123 | open | `4f9d0e8` | next sync | none of the five fixes changes V4.1 output | none |
| #777 | open | `9cb0271` | next sync (no-op) | swapped extents compile identically while NR1=NK=32 (`moe.metal:7141-7143`) | none |
| #1089 | open | `f6639cf` | drop: output (owner rule) | V4.1 live rewind through an 8192-row raw ring; measured on the target | server multi-turn TTFT high; +640 MiB per session |
| #1010 | open | `c39be7b` | not reachable | CPU cache and generic `metal_graph_*` only; `ds41_graph_alloc` untouched | none |
| #957 | open | `f22be7b` | drop | old base conflicts with `660e1d4b`; rewrites the map function V4.1 streaming uses | risk |
| #420 | open | `0bf5938` | already in main (`d75e23d3`) | counters under `g_tensor_mu` (`ds4_metal.m:1139-1195`) | none |
| #1027 | open | `ee2e3a8` | next sync (one of the pair) | same fix as #873; calls `getenv` per piece; advertised `DS4_BPE_VERIFY` does not exist | low |
| #873 | open | `142d95b` | next sync (preferred) | same heap BPE, smaller, no env switch, tie stress test | low |

**Commit notes.**

- **#1061 `6856a23`.** Above n_comp ≥ 1024, `ds41_attention_select_published`
  routes to `kernel_dsv41_indexer_scores_decode` (simdgroup 8×8 MMA) instead
  of `kernel_glm_indexer_score_one_direct`.
  - Side effects: V4.1 prefill chunks of 1-7 tokens also switch; `--quality`
    decode falls to the slow scalar batch kernel through `force_scalar`; the
    `DS4_METAL_V41_INDEX_CHECK` block ends and restarts batches (do not port).
  - Claims: M5 Max standalone, 0.50 ms per token at 435K rows (at the key-read
    floor); max |diff| 8e-10 against a double reference; 16K greedy output
    byte-identical.
  - Transfer: about 1-3 ms per token at 32K, 5-12 ms at 128K.
  - A bitwise route exists. Keep score_one_direct's reduction: one `simd_sum`
    per head, lane l holding dims 4l..4l+3, heads summed 0→31 from +0.0. Load q
    into threadgroup memory once and stream many rows per simdgroup.
- **#1060 `be6a8ce`.** It hooks `ds4_gpu_indexer_topk_tensor_impl`, so it covers:
  - decode top-512 on layers 20/24/28/32/36 from pos 4095 and on layers
    2/8/14 from pos 8191;
  - the layer-20 block top-k from pos 32767;
  - prefill at the same widths.

  A batch straddling 4096 is split, which keeps `check_causal_topk`
  (`tests/test_deepseek41_metal.c:955`). Claims (M5 Max, Q2, SSD streaming):
  435K×1, k=512 goes from 1.7-2.4 to 0.4-1.0 ms per call, and 16K greedy
  output is byte-identical. The prefill 169 → 178 t/s is noise. Transfer:
  about 0 below 16K, under 1 ms per token at 32K, 2-4 ms at 128K, about 9 ms at
  435K.

  **When its output differs** (eligible only at width ≥ 4096, top_k ≤ 2048,
  n_comp ≤ 4,194,304, and `DS4_METAL_DISABLE_TOPK_SELECT` unset):
  1. *Set.* The k-th score ties with a row outside the top-k. Main keeps
     whatever the bitonic network leaves inside the 1024-row block, with
     earlier blocks winning; the select keeps the lowest indices.
  2. *Order, decode top-512 only.* Two selected rows tie in the same block.
     Main's network is not stable: `[2, 1a, 1b, 3]` → `[3, 2, 1b, 1a]`. The
     select emits indices in ascending order. Decode gathers KV in top-k order
     (`ds4_gpu_dsv41_gather_kv`), so attention's summation order changes. The
     PR's "identical whenever the k-th score is not tied" misses this case.
  3. *Key semantics.* The integer key puts −0 below +0 and NaN above +inf.
     This is unreachable for V4.1.

  Main's sort is deterministic run to run (a data-independent network, no
  atomics), but it is not a total order, and tie order can change between
  decode steps.
- **#959.** `4b9ff60` is exact: the first k outputs of a stable merge depend
  only on the first k of each run. `e8c84dd` is its test; `b4605a0` is an
  optional refactor. It covers only the non-causal path; main's causal path
  already caps reads at 512 (`bd66c402`).
- **#832.** Commits `35e99af`, `fc2db34`, `4ff3a5b` and `d1d53ef` are
  patch-identical to #830/#831. `828e141`, `09ca18f` and `eb2e545` (canon
  comparator) are dropped:
  - V4.1 decode (`ds4.c:24004`), the layer-20 blocks (`ds4.c:23990`) and prefill
    rows under 1024 wide call the non-causal kernel;
  - the causal batch keeps network order, so decode and batch ids stop
    matching (predicted failure of the j%7 tie pattern).

  `79d3cef` (stream512) is unreachable (`!causal && n_tokens >= 32`), and main
  removed an earlier stream512 as non-reproducible (`023614e`).
- **#758 `e154aa8` rb16.**
  - Gate: `prefill_dual_heads`, `n_tokens >= 32`, device "M5 Max".
  - The dual kernel is identical at the PR base and in the child.
  - Its `break`→`continue` is equivalent, because prefill sorts ids first
    (`ds4_metal.m:28221`).
  - Claims: M5 Max, V4 Flash resident; attention stage −11%, prefill +2.9%,
    logits byte-identical.
- **#1123.**
  - `a54b5b0` patches `metal_graph_prefill_chunked_range`, which the child
    deleted. V4.1's `raw_prefill` holds `prefill_cap + 128` rows
    (`ds4.c:23501`), and a chunk never exceeds `prefill_cap`.
  - `04b6423` and `4f9d0e8` touch kept layer-slice code and merge cleanly.
  - `afab7d6` is a no-op (TP world ≤ 2).
  - `b354216` concerns resident dumps only.
- **#1089 `f6639cf`.**
  - Claims (M5 Max, Q2, streaming, 52 GB expert cache): a turn at 21K goes from
    54.6 s to 7.3 s; a batched 3-turn session from 631 s to 245 s.
  - A rewound state equals "prefix then tail" bitwise, not a fresh single
    sweep: logits differ by 0.57-0.92, the same noise floor as main's staged
    against fresh prefill.
  - Server paths only. 640 MiB per session by default (`DS4_V41_RAW_LOG_ROWS=0`
    disables it). TP rewind is untested.
- **#1010.** V4.1's compressed caches are about 210 MB at 32K and 6.7 GB at 1M,
  allocated up front in `ds41_graph_alloc` (`ds4.c:23700`). A lazy-growth port
  would be an idea for 1M contexts only.
- **#957.** The same map function serves the V4.1 SSD initial map
  (`ds4.c:30184`), the streaming prefill map and the TP shard map. The
  merged-span path skips the view-lifetime handling from `660e1d4b`.
- **#873 / #1027.** `bpe_emit_piece` is used by V4.1 tokenisation
  (`ds4.c:25848` → `25914`). Both use a linked list plus a heap by (rank,
  leftmost), so ties break as before and tokens are identical.

Long contexts are realistic here: the V4.1 context costs about 7 KB per token
(`ds41_graph_bytes`), so 128K-1M fits beside the expert cache. The owner's
typical band is 1-10K, so the long-context items are history.

## 7. SSD streaming

**Correction to the brief** (verified in section 2): the decode Engram is not
read serially. `ds41_graph_step` (`ds4.c:24509`) calls `ds4_engram_read_batch`
once per table, and each 24-row batch uses 16 `dispatch_apply_f` readers
(threshold 8 rows).

| PR | State | Head | Verdict | Reason | Effect (decode / prefill) |
|---|---|---|---|---|---|
| #1033 | open | `36aecab` | adopt only if measurement confirms | opt-in (53 lines in `ds4_metal.m`): owned expert slabs in a Metal residency set attached to the queue; dry run applies cleanly | none to high, unknown (any per-submission cost is paid about 81 times per token) / low |
| #1035 | open | `ce0c537` | superseded by `6c00e2d` + `077a257` | the child already reads with 16 workers; its hook would only fire in `ds41_graph_step_batch` (non-streaming) | none |
| #849 | open | `9b4bb9e` | idea (needs a port) | inert on V4.1 as written: F16 routers only (V4.1's `ffn_gate_inp` is F32), relies on hash layers (V4.1 has `n_hash_layer` = 0), GLM hunk on removed code | decode medium but uncertain / none |
| #848 | open | `1bc2fac` | drop | needs a 142 GiB sidecar or hole-punched expert space; the gain is probably an artefact; correctness hazard (see below) | low / none |
| #570 | open | `66ca6ef` | adopt `a1afb82` (stats); `66ca6ef` drop | pool queue depth and GB/s in the timing summary; the QoS pin matters only in background launches | none (measurement) |
| #533 | closed | `20df520` | drop (withdrawn) | turning off the miss read-ahead by default regressed main's prefill (M5 Pro); V4.1 issues the hint on the eval thread, the GLM case where skipping it gave +13% | decode low-medium, testable with an existing switch |
| #514 | closed | `40d8de2` | drop | closed by the author as useful only on low-RAM machines; its Q4 knobs drift tokens | none |
| #499 | open | `d6a800e` | superseded by `22e41728` | static weights already locked (9.37 GiB) | none |
| #725 | open | `d7716f5` | drop | a 240-slot floor; the cache holds about 8090 slots | none |
| #454 | closed | `356b450` | not reachable | `ds41_moe_batch` passes `force_resident = true`, so prefill never takes the batch selected-address path | none |
| #73 | open | `c5d6349` | drop | CPU `--low-mem` on a May base | none |
| #24 | closed | `c20e478` | drop | predates SSD streaming; rejected upstream | none |
| #307 | open | `e5455bb` | not reachable | CPU-only hooks; Metal `DS4_EXPERT_PROFILE` is wired only into the old `metal_graph` path | none |
| #822 | open | `b26a33c` | not reachable | its `metal_graph_prefill_*` and `test_engine_mgpu_placement.c` are gone | none |
| #850 | open | `7e8fd8b` | not reachable | `ds4_effective_prefill_chunk` is gone; V4.1 overrides `prefill_cap` (`ds4.c:31174`) | none |
| #464 | open | `5e86cc4` | not reachable | V4.1 refuses `--power` below 100 | none |
| #1117 | open | `144852e` | not reachable | Linux only; the Metal equivalent is in the child | none |
| #1082 | closed | `5e46ff5` | superseded by #1083 | wrong branch | none |
| #1083 | open | `4c82792` | not reachable (CUDA); Metal counterpart already in main | see below | none |
| #1056 | open | `b1af94b` | not reachable | its SSD commits are Qwen-gated | none |
| #647 / #739 / #738 | open | `ab98473` / `05632d2` / `e747490` | not reachable (CUDA) | the Metal cache already has per-(layer, expert) entries with decayed hotness plus LRU tie-break, pooled slabs and a byte budget; unified memory has no upload step (preads land in shared slab slots) | none |

**Commit notes.**

- **#1033 `66f757b`.** With `DS4_METAL_STREAMING_SLAB_RESIDENCY=1`,
  `ds4_gpu_stream_expert_alloc_slab_buffer` adds each slab to a residency set
  (`addAllocation` + `commit`), attached to the queue once. The set is removed
  in `clear_all` and after mlock relief.
  - Measured on M2 Ultra 192 GB, macOS 15.7.4, 135 GiB pool: 0.24 → 9.31 t/s
    for an 8-token decode, about 13.4 steady, identical output.
  - Their model-free repro showed about 250 ms of driver time per submission
    with a 104 GiB pool, and nothing at 32 GiB.
  - Our pool (17 × 4 GiB) is the same ~53% of RAM as their 104 GiB case. At 6
    t/s there is no full cliff here, but a partial cost is plausible.
- **#849 `60051d4`.** A background thread runs layer L+1's router on layer L's
  input and pre-reads the predicted experts into staging buffers, which demand
  reads consume by memcpy. A retain mark protects the predicted experts. Output
  bytes cannot change.
  - Measured on M4 Max 36 GB, V4 Flash MXFP4, about 1,200 slots: +5.2% only on
    top of #848, −5.5% without it.
  - Its "top-4 covers 46% of misses" was measured with 256 experts; V4.1 has
    384.
  - The port needs F32 router registration and dropping the GLM and hash-layer
    parts. Its note-x hook in `ds4_gpu_routed_moe_one_tensor` is reached by
    V4.1.
- **#848 `1bc2fac`.** The +10.7% came with a *higher* average read time. Its
  unpacked baseline had just been rewritten by `--restore`, so its extents were
  likely fragmented. Each slice is already a single 2.9-3.7 MiB pread, and NVMe
  has no seek cost.
  - **Hazard:** the packer frees the GGUF's expert space by default. V4.1
    prefill maps whole layers through mmap and seeds the cache from them,
    bypassing the pread zero guard, so it would silently compute on zeros. It
    would also break the HF cache blob and the parity oracle's upstream run.
- **#570.** `a1afb82` prints dispatches, `qd_avg`, `pool_gbps` and `task_gbps`.
  `66ca6ef` sets user-initiated QoS and `IOPOL_IMPORTANT`, which is neutral in
  the foreground (M1 Ultra, M5 Pro).
- **#1083.** Metal already has the counterpart:
  `ds4_gpu_stream_expert_split_worthwhile`, `begin_selected_load`, the masked
  address-table kernels and a 9-thread pread pool.
  - Metal splits a layer only with at least 3 misses, at least 4 decode tokens
    and at least 1,024 cached entries.
  - It then runs one fused sum6 down pass after all misses land, with no
    per-slot down split and no gate/up-before-down read ordering.
  - The hits' compute is about 0.1-0.2 ms per layer, so the remaining gain is
    small.
- **#1056.**
  - `e2b4a47` hooks only `prepare_selected_batch` (used only when
    `force_resident = false`). V4.1 decode does one 30,720-entry
    `take_reusable_batch` scan per layer with misses.
  - `9e1429b` is Qwen MTP admission.
  - `e37f185` assumes 512 experts and top-10 routing.
  - The heap idea would trim only V4.1 prefill seeding (about 1,240 scans per
    sweep, under 1%).

**Where a ~160 ms decode token goes** (a code model, not measured):

| Part | Estimate | Detail |
|---|---|---|
| Engram | about 0.6-1 ms | 2 × 24 random 264-byte reads before GPU work; table 1 is not needed until layer 14 |
| command buffers | about 15-20 ms | about 81 per token, each a commit and a full wait. Per layer: attention + router + shared expert, ended by the id readback; routed MoE, ended by the drain; plus the logits. #1034 recovered about 10 ms by removing 39 drains on M2 Ultra |
| GPU compute | about 40-50 ms | resident V4.1 Q2 runs at about 20 t/s on M3 Ultra, per `6c00e2d` |
| host bookkeeping | about 2-6 ms | a victim scan per layer with misses; three `F_RDADVISE` per miss on the eval thread; installing loaded experts |
| miss service | about 90-120 ms | (1−h) × 240 × 9.95 MB at 6-8 GB/s, for h ≈ 0.7 |

Miss service is serialized with GPU work: the split rarely fires at 1-2 misses
per layer. Expert preads go through the page cache (`g_model_fd` is a plain
`O_RDONLY`, without `F_NOCACHE`). This is the only term large enough to explain
6 t/s against antirez's 13.39 t/s.

Which PRs attack which part:

| Part | PRs |
|---|---|
| miss count | none |
| miss latency | #849; the existing Metal split |
| miss bandwidth | #848 (doubtful); the #533 lesson; pread thread count |
| syncs and submission | #1033; #1034/#1041 |
| Engram | already solved |

**Order.**
1. Baseline with the existing switches: `TIMING_SUMMARY`, `LAYER_STATS`,
   `PREAD_PROFILE`, `CB_TIMES`, `GPU_BUSY_PROFILE`, and
   `DS4_MOE_RECORD_SELECTED_IDS` for an offline cache-policy simulation. The
   last one flushes after every record, so run it separately.
2. A/B tests without code:
   - `DS4_METAL_DISABLE_STREAMING_EXPERT_READAHEAD=1`;
   - `DS4_METAL_DISABLE_STREAMING_EXPERT_SLABS=1` and `SLAB_MB=512`;
   - `PREAD_THREADS` at 4, 9 and 18;
   - #1033's model-free bench with `toggle 17 4096 4080 24 6`.
3. #570 `a1afb82`.
4. #1033, if a submission delay shows up.
5. #849, if reads are latency-bound and the SSD sits idle.
6. #848: never, as it stands.

**The child cannot measure yet:** decode Engram time; a per-token V4.1 decode
breakdown (`DS4_TOKEN_TIMING` is CPU-only, `DS4_METAL_V41_STAGE_PROFILE` is
prefill-only); pool queue depth and bandwidth (#570 adds them);
`DS4_EXPERT_PROFILE` for V4.1.

**Risks.**
- Cache state dominates the numbers: fresh engine per arm, the same prompt,
  ABBA, a fixed cache, the hit rate reported per arm, and the page cache
  controlled.
- #1033 keeps 68-75 GiB resident for the GPU on every submission, interacts
  with mlock relief and depends on the macOS version: keep it opt-in until it
  is measured.
- #849 costs extra SSD traffic, staging RAM and a CPU thread, and its retain
  mark changes hit counts by design.
- Read-ahead off may hurt cold starts: it gave 3-4× faster per-read throughput
  on M5 Pro.

## 8. MoE and quant kernels, and older Metal work

Nothing here speeds up V4.1 decode under streaming in a way this machine could
measure. The candidates are the SSD I/O and scheduling commits of #952 and #621,
plus one small prefill change from #864. First pass by three nested subagents;
the recommended commits were spot-checked.

| PR | State | Head | Verdict | Reason | Decode / prefill |
|---|---|---|---|---|---|
| #864 | open | `482e246a` | idea (the LUT only, hand port) | the half-LUT dequant reaches V4.1's packed MPP gate/up kernel; the split-MPP rewrite only runs on 32-511-row tails; conflicts with main | none / low |
| #1120 | open | `b824ea6d` | history (resident) / next sync if merged | the V4.1 Q2 sum6 shape exists only in the resident kernel | none / none |
| #559 | closed | `3d185eab` | drop | atomic float adds, nondeterministic order; the simdgroup path it changes is unused on M5 | none |
| #306 | closed | `6bfe54f4` | drop | measured on M5 Max: 30.1 → 14.6 t/s decode | none |
| #555 | closed | `97efe609` | already in main (`427e281d`) | its M5 part already runs in V4.1 prefill | none |
| #15 | closed | `b109d851` | in main, modified | squashed as `63ceed6a`; routed-MoE TensorOps removed (`d4fba7b1`), then rebuilt as packed kernels (`2ea3839e`, `bd66c402`) | none |
| #149 | closed | `b111079b` | superseded | scratch change in main; chunk sizing replaced by `ds41_prefill_limit`; barrier removal touches legacy kernels only | none |
| #954 | open | `1b57506c` | not reachable; one idea (history) | MXFP4, pre-M5, ratio-4 or old-graph; `0c2a0d53` (`attn_out_low` static trip) matches V4.1's shape but is pre-M5 gated | ≈0 / none |
| #874 | open | `d06eba3a` | history (near zero) | `595e06da`, the matvec reduce tree on simdgroup 0 only, is bit-exact and device-agnostic and hits `kernel_mul_mv_q8_0_f32`; the rest is V4 Flash | ≈0 / none |
| #902 | open | `3a84f407` | drop | M2-only whitelist | none |
| #770 | open | `dfea3a79` | drop | the predicate swap changes nothing on "Apple M5 Max" | none |
| #846 | open | `8b08c21d` | drop | M1-only gates; the n-gram speculation needs a verifier | none |
| #778 | open | `d81a28f2` | not reachable (DSpark parts n/a) | HC spread and FFN-island-into-HC only in `metal_graph_encode_decode_layer_phase` (`ds4.c:16065`) | none |
| #418 | open | `2c547138` | not reachable; FP8 store lossy | old-graph KV code; V4.1's compressed KV is already FP4/FP8 and about 200 MiB at 32K | none |
| #952 | open | `e9cc3d73` | adopt `a2e2ea53`; ideas below | based on `0aaea5a`, with V4.1-specific SSD commits | low-medium / medium (uncertain) |
| #621 | closed | `6a20b131` | superseded by #952, except its SSD-read ideas | split preads target the real bottleneck | medium (uncertain) / none |

**Commit notes.**

- **#864.** The IQ2_XXS half LUT goes into `dequantize_iq2_xxs` (`moe.metal:797`).
  The packed kernels (`:7112`, `:7115`) and the MPP kernel (`:7323`) use it.
  - All 2048 entries equal 0.25 × the grid byte exactly (checked with a
    script). The sign is a bit flip, and the f32→f16 store is unchanged.
  - The Metal library compiles with fast-math by default
    (`ds4_metal.m:6514-6531`), so it still needs an on-device bitwise test.
  - Split MPP (one 32-row op → two 16-row ops) may change the accumulation:
    drop: output.
  - Claim: V4 Flash resident, M5 Max, +5-8% prefill.
- **#1120.** Streaming exclusion is structural. The shaped pipelines are
  instances of the resident kernels (`kernel_mul_mv_id_q2_K_sum6_f32`
  `moe.metal:4117`, pack2 `:1943`), which read whole-tensor buffers.
  - Streaming V4.1 decode dispatches the slots6/addr/masked kernels instead
    (`ds4_metal.m:34296-34613`, `34872-34943`).
  - Porting its shape constants into `kernel_mul_mv_addr_q2_K_sum6_masked_f32`
    (`moe.metal:4419`) would be bit-exact but worth about 0.05%.
- **#952.**
  - **`a2e2ea53` (adopt).** It fixes loading into a full cache: the service
    thread waiting on GPU work, allocation past the budget, a non-atomic
    `done_seq`, and lost slab slots. That is exactly our situation. No
    arithmetic changes.
  - **`a3043bb2` (idea → `50`).** Missing-expert reads start right after
    routing, overlapping the shared expert; it also fuses BF16 rounding with
    RoPE.
    - It hooks `ds41_moe` through
      `ds4_gpu_glm_stream_expert_cache_begin_selected_load_tensor`. The GLM
      prune removed that function and `_prefetch_set` from the child; main
      has them at `ds4_metal.m:17221-17340`.
    - The child's consumer `_prefetch_take` (`:16091`, called at `:33493`)
      never fires.
    - Measured on M1 Max: 2.43 → 2.44-2.50 t/s.
  - **`bac91c21` + `c12d639a` (idea → `60`).** Single-chunk SSD prefill of up to
    about 2048 tokens preads each layer's experts into two locked Metal buffers
    and overlaps the next read with compute. Gated pre-M5, with no device
    dependency in the code. M1 Max 32 GB, 437 tokens: 4.05 → 14.7 t/s,
    byte-identical text.
  - **Small bit-exact fusions, each under about 1%:** `2b9d1c20`, `9f7e4eb6`,
    `2da41a49`, `5d83b550` (needs `0edc5534`) and `ecf0b138`, plus
    indexer/mask skips. These are in the `70` code zone, so history.
  - **`2c9d48fe`** changes what a manual cache size means (it subtracts the
    fixed weights first). At a sync, re-check that the 75 GiB dynamic cache
    still means the same thing.
- **#621.**
  - `8f5a7458` splits each expert pread into up to N 16 KiB-aligned pieces on
    the same pool. It is opt-in, reads the same bytes, and measured +16% decode
    on M1 Pro, bit-identical. The child reads one task per expert tensor
    (`ds4_metal.m:12226`, `12493`) with 9 threads by default (18 at most).
  - `f7695ea0` adds an optional `F_NOCACHE` descriptor for expert reads.
  - `61e35e22` is a live-entry index for eviction, V4 Flash-sized (the child
    scans all 30,720 entries): open.
- **#778.** `c813ff15` (standalone as #777) fixes the `tB` extents in the MPP
  kernel. It is bit-identical and missing in the child (`moe.metal:7211`):
  next sync.

**What V4.1 dispatches on M5 (child tree).**

- **Streaming decode** (`ds4_gpu_routed_moe_one_tensor`, force_resident = false):
  - Steady state (at least 4 decode tokens and 1024 cached entries,
    `ds4_metal.m:13115-13140`, `13270-13290`):
    - gate/up: `kernel_mul_mv_addr_iq2_xxs_pair_swiglu_masked_f32`
      (`moe.metal:2331`);
    - down: `kernel_mul_mv_addr_q2_K_sum6_masked_f32` (`moe.metal:4419`).
  - With 3 or more misses, the hits-first split (`ds4_metal.m:34309-34529`):
    resident experts, then the missing ones, then one down pass over all six
    in fixed order.
  - Warm-up: `kernel_mul_mv_slots6_iq2_xxs_pair_swiglu_f32` (`:2095`) and
    `kernel_mul_mv_slots6_q2_K_sum6_f32` (`:4216`).
  - The resident `kernel_mul_mv_id_*` kernels run only for force-resident rows
    in the sweep and for 2-8-row batches (`ds4_metal.m:35378`).
  - Q8_0: `kernel_mul_mv_q8_0_f32` (`dense.metal:187`), via
    `ds4_metal.m:17973-18030`.
  - `output_a`: `kernel_dsv4_attn_out_low_q8_0_f32` (`moe.metal:1610`).
- **Prefill** (`ds41_moe_batch`, force_resident = true, `ds4.c:24490`):
  - always: `kernel_mul_mm_id_map0_ne20_6` (`moe.metal:6043`) and
    `kernel_moe_pack_rhs_f32` (`:7001`);
  - 512-8191 rows: `kernel_mul_mm_id_iq2_xxs_mpp_packed` and
    `kernel_mul_mm_id_q2_K_mpp_packed` (`:7034`, `:7112-7113`);
  - 8192-row chunks: `*_mpp_packed_m32n128` (`:7115-7116`);
  - 32-511-row tails: `kernel_mul_mm_id_iq2_xxs_f32_mpp` and
    `kernel_mul_mm_id_q2_K_f16_mpp` (`:7122`, `:7323-7324`);
  - Q8_0: `kernel_mul_mm_q8_0_f32_nax_direct_rhs{,_n64,_n128}`
    (`dense.metal:2133-2135`), with `kernel_mul_mm_q8_0_f32`
    (`dense.metal:2558`) for leftover rows;
  - `output_a`: `kernel_attn_out_low_q8_0_mpp_direct_rhs_n64` (`moe.metal:7560`).
- **Prefill policy:** see section 2. Decoder layers 20 and up use 2048-row
  chunks over the dependency suffix only (`ds4.c:24930-24945`).

**Risks.**
- "Exact in IEEE" is not "identical code generation" under fast-math: demand
  on-device bitwise checks.
- The cache size is near a threshold. 75.5 GiB is only 6% above the
  half-cache line (7680 slots), and crossing it switches appends under 1024
  tokens between token-major and layer-major. That is a policy change, not a
  regression.
- Early loading (`a3043bb2`) changes when cache slots are reserved: take it
  after `a2e2ea53`.
- More readers (split preads) compete with the disk-only Engram reads. #846
  found 18 threads alone, or preloading, neutral or worse on M1 Ultra.
