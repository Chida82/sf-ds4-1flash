# Design

## Context

See proposal.md (Why). Facts from the code and the PR diffs that shape the
port:

- **The loop today** (`ds41_graph_step`, `ds4.c:24506`): one command batch
  is opened before the layers; `queue_layers` is true only for the TP pair
  (`g->tp_world == 2 && !DS4_METAL_DISABLE_V41_TP_DECODE_QUEUE`); with it off,
  `drain` is true at every layer, so every layer ends with
  `ds4_gpu_end_commands()` (commit and `waitUntilCompleted`) and a fresh
  `ds4_gpu_begin_commands()`. With it on, the drains are at layer 13 (the
  second Engram table's rows are written into the same `engram_rows` buffer
  at layer 14, so the GPU must be done with the first) and at the last layer
  (the logits are read by the CPU). `layer_resident` (`streaming && quality`)
  maps one layer at a time and ends the batch itself. The child has no
  `imatrix` field: the `!g->imatrix` term of the upstream diffs is dropped.
- **Inside a layer, streaming reads the selected ids back** in
  `ds4_gpu_routed_moe_one_tensor` (`ds4_metal.m:33533-33558`): a signal-and-
  wait on the batch (or an end/begin) so the CPU learns the six experts and
  loads the missing ones. That round trip is per layer and stays; the queue
  removes only the layer-end drain. This is why the M2 Ultra streaming gain
  (+13.5%) is a third of the M3 Ultra resident one (+37%).
- **`ds4_gpu_flush_commands`** (`ds4_metal.m`) already exists: it commits
  the open batch without waiting, appends it to `g_pending_cbs`, and opens
  the next one. `ds4_gpu_end_commands` waits. Both notify the expert cache
  (`note_batch_committed` / `note_batch_created`).
- **#1041 `bd6f912`** (36-line diff): `queue_layers` on one box, switch
  `DS4_METAL_DISABLE_V41_DECODE_QUEUE`; after every non-drain layer a
  `ds4_gpu_flush_commands()` unless `DS4_METAL_DISABLE_V41_DECODE_FLUSH`. The
  flush is guarded by `!layer_resident` but the queue is not: with
  `--quality --ssd-streaming` the loop's per-layer `begin_commands` finds the
  batch open at layer 1 and fails. Its flush also runs for the TP pair.
- **#1073 `2a281b08`** (111-line diff): the same queue with
  `!layer_resident`, the flush every `DS4_METAL_V41_DECODE_FLUSH_LAYERS`
  layers (default 2) and only for `tp_world != 2`; a second buffer
  `engram_rows_b` written before the token with the first, which removes the
  layer-13 drain on one box (TP keeps it); the same flush in
  `ds41_graph_step_batch`. **`29ce2717`** (12 lines) aliases
  `row.engram_rows_b = row.engram_rows` in the prefill sweep, whose rows hold
  whichever table the layer reads.
- **#1034 `9b50495`**: its queue is an opt-in `DS4_METAL_ENABLE_V41_STREAM_
  DECODE_QUEUE` without the flush; its test `check_stream_decode_queue` opens
  the engine with `ssd_streaming_cache_experts = 512`, syncs 120 tokens into
  one session, snapshots it into a second, decodes 24 tokens in both with the
  queue off and on, and compares logits, `ds41_graph.history` and the state
  spans (`ds41_state_spans`, which the child's test already uses) bitwise.
  Its bench flag adds `--ssd-streaming` to `metal_decode_schedule_bench`.
- **The batch step** (`ds41_graph_step_batch`) never runs under streaming on
  this machine (registry, #1035): the batch hunk of `2a281b08` is not taken.
- **Measured baseline** (`speed-bench/perf-record.md`): a decode token at 8K
  is 56 ms, of which 38 ms wait for missing experts inside the layers; the
  layer-end drains are part of the remaining 12 ms of GPU and host time,
  plus whatever GPU idle they cause between layers. The token-major tails of
  `cold-2500` and `cold-5000` run the same function at 58 ms per token.
- **Harness noise** (`speed-bench/README.md`): `decode 8192` and `ttft 5000`
  are the tight metrics (±2%, four pairs); `decode 2048` needs pooling.

## Goals / Non-Goals

**Goals:**
- The one-box queue with the flush, bit-identical, with upstream's switch
  names so the eventual sync of #1041 or #1073 lands clean.
- One mechanism at the end: S1's per-layer flush or S2's period and second
  Engram buffer, whichever the keep rule prefers.
- The forced-eviction test and the same-engine schedule bench, so a future
  change to the loop has a model-backed guard besides the harness.

**Non-Goals:**
- The TP pair's queue and drains: untouched, unmeasurable here.
- `ds41_graph_step_batch`, the resident-only tail (#1041 `fdbf7f2`), #1067's
  one-wait token, #1049.
- The per-layer selected-id readback and the miss reads: `50-ssd-miss-overlap`.

## Decisions

### D1. Three steps, each measured against the previous

- **S0, tool.** Port `check_stream_decode_queue` from `9b50495` into
  `tests/test_deepseek41_graph.c` as `--stream-decode-queue-parity`, with the
  control setting `DS4_METAL_DISABLE_V41_DECODE_QUEUE=1` and the candidate
  unsetting it (the switch S1 adds; before S1 both sessions run the drained
  loop and the test passes trivially, which is the right baseline). Add
  `--ssd-streaming` and `--ssd-streaming-cache-experts N|NGB` to
  `speed-bench/metal_decode_schedule_bench.c`, passed through to
  `ds4_engine_options` as `ds4_bench.c` does. No speed claim: bitwise output
  and no metric below zero is the tool rule.
- **S1, the queue.** `bd6f912` with three edits: no `imatrix` term;
  `queue_layers` also requires `!layer_resident`; the flush requires
  `g->tp_world == 1`. Names `DS4_METAL_DISABLE_V41_DECODE_QUEUE` and
  `DS4_METAL_DISABLE_V41_DECODE_FLUSH`; the drains at 13 and 39 stay.
  Target metric `decode 8192`; guards `guard-decode`; `ttft 2500` and
  `ttft 5000` measure the token-major tails.
- **S2, the variant.** `2a281b08` minus its batch hunk, plus `29ce2717`: the
  flush every `DS4_METAL_V41_DECODE_FLUSH_LAYERS` layers (default 2, 0 for
  none) replaces `_DISABLE_V41_DECODE_FLUSH`, and `engram_rows_b` removes the
  layer-13 drain when `tp_world == 1`. Measured against S1. If S2's pooled
  interval on `decode 8192` is not above zero, S2 is reverted whole and S1
  stays; if it is, S2 stays and S1's flush switch goes. The two halves are
  not split: the layer-13 drain is one drain in forty, and a period knob
  alone is a one-line variant of S1 whose difference the harness cannot
  resolve.

Alternative: S2 first, S1 never. Rejected: S1 is the smaller diff with the
upstream measurement in our regime, and a sync of #1041 would then land
clean; S2 has to earn its extra buffer.

### D2. Where each switch is read

Once per token, at the top of `ds41_graph_step`, as the PR does; the loop is
40 layers per token and `getenv` per layer would be measurable. S2's period
is cached in a static, as `2a281b08` does.

### D3. Correctness evidence

- `ab_bench.py --bitwise` against the previous step: tokens and logits after
  every prefill and decode frontier, for `decode`, `cold-2500`, `cold-5000`.
- `--stream-decode-queue-parity`: the forced-eviction case the harness's
  75 GiB cache never reaches (512 slots, two sessions, evictions between the
  queued layers of one token).
- `metal_decode_schedule_bench --ssd-streaming --ssd-streaming-cache-experts
  82GB --candidate-env DS4_METAL_DISABLE_V41_DECODE_QUEUE --include-selection`:
  the rollback as candidate on one engine, which aborts unless every logit
  row is bit-identical and the selected tokens match; its ratio is a
  same-engine cross-check of the harness's verdict, not the verdict.
- `--quality --ssd-streaming`: one CLI prompt decodes (the `layer_resident`
  fix), tokens compared with `main`'s.
- Expert-cache counters equal between A and B on every frontier: the queue
  must not change what is loaded or when.
- Parity at the end.

### D4. Measurement plan

Start row first (design D14 of `20`): `git worktree add ../sf-ds4-1flash-start
7dea5e3`, A/A `--kinds decode,cold-2500,cold-5000 --guards guard-decode`,
row pasted into `perf-record.md` segment 1. Then per step an A/B of the same
kinds, A being the previous step's tree (the start worktree for S1, a
worktree of S1's commit for S2), `--bitwise`, default budget; pooled with a
second invocation when `decode 8192`'s interval straddles zero. The final
tree against the start worktree gives the change's record row.

### D5. Docs and registry

`speed-bench/README.md` (schedule bench section: the two flags and the
rollback command); the switches documented next to the other
`DS4_METAL_DISABLE_V41_*` names in `docs/SSD_STREAMING.md` or `docs/METAL.md`,
wherever they live; registry lines #1041 `bd6f912` (adopted, measured),
`fdbf7f2` (unchanged), #1034 `9b50495` (tool adopted), #1073 `2a281b0`
`29ce2717` (kept or dropped by measurement), #1067 and #1049 (unchanged,
cited by the proposal).

## Risks / Trade-offs

- [The queue changes the timing of the selected-id readback and the async
  expert loads] → bitwise gate, the forced-eviction test, equal cache
  counters; a failure there stops the step.
- [The gain is smaller than the harness resolves] → `decode 8192` at ±2%
  with four pairs; a second invocation pooled; the +13.5% of the M2 Ultra
  suggests it is well above.
- [`ds4_gpu_flush_commands` returning 0 when the next buffer cannot be
  created] → the loop fails the token as it does for any other error; the
  PR's path is unchanged.
- [Sync conflict] → one site in `ds41_graph_step`, upstream's own text where
  possible; S2's tensor macro line and the sweep alias are upstream's lines.
- [The test's 512-slot cache opens the model with the auto budget elsewhere]
  → it sets `ssd_streaming_cache_experts = 512` as the PR does; on this
  machine that is a 4.7 GiB cache and a fast open.

## Migration Plan

Additive; the switches restore the drained loop. Rollback is a revert of the
squash commit.
