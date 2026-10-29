# Design

## Context

- **DeepInfer's YOCO truncation.**
  - **Switches.** `DEEPINFER_YOCO_PREFILL_TRUNCATION_MODE` takes `off` (default), `mask` or `compact`, and `DEEPINFER_YOCO_PREFILL_KEEP_TOKENS` sets K (`deepinfer/environ.py`). K must be at least the window plus the speculative back-tracking tokens, and must be set explicitly.
  - **Where the cut starts.** `_n_prefill_layer` (`deepinfer/hugging_face/config.py`) makes the first ratio-1 layer the last full prefill layer: "it and everything before it form the prefill side, the layers after it are yoco consumer layers".
  - **What `compact` does.** It removes the truncated queries from the consumer layers (`deepinfer/model_executor/input_metadata/yoco.py`).
  - **Known side effects** (`deepinfer/engine/llm_engine.py`): `prompt_logprobs` is forced off, and preemption is allowed to change results.
- **This child's schedule** (`ds41_prefill_count`, `ds41_graph_prefill_sweep`, `ds4.c`):

  | Shape | Sweeps | Decoder work today |
  |---|---|---|
  | `cold-2500` | one 2048-row sweep, then 452 rows token by token | the sweep is not wide (`ds41_encoder_chunk_cap` is 2048 below 8192), so all 2048 rows go through layers 20-39 |
  | `cold-5000` | one 4096-row wide sweep, then 904 rows token by token | the decoder suffix: `1 + (39 - il) * 127` rows per layer, short-sweep tiles of 2048 |
  | `cold-10000` | an 8192-row wide sweep, then a 1808-row sweep | the suffix in the first sweep (about 4 s); all 1808 rows through every layer in the second (10.3 s for the whole chunk) |

  These shapes are read from the code and must be confirmed by task 1.1's profile.
- **Attention window** (`ds41_attention_batch`).
  - **The raw buffer.** It holds `previous = min(start, 127)` rows copied from the layer's ring `g->window[il]`, then the batch's rows.
  - **The window.** The Metal kernels compute `first_raw_pos = pos0 + n_tokens - n_raw`, and each query sees `[max(first_raw_pos, qpos + 1 - window), qpos]`. That covers the indexed mixed attention in `metal/dsv4_misc.metal`, and the mixed and raw batch masks in `ds4_metal.m`.

  A segment start is therefore a C-side argument: with `previous = 0` at the segment's first row, `first_raw_pos = s`, and the kernels exclude everything before it unchanged.
- **The ring after prefill.** The end of `ds41_attention_batch` writes back the last `min(n_raw, 128)` rows. A decode step reads `min(pos + 1, 128)` rows ending at its position.
  - With K ≥ 128, the ring then holds exactly the segment's last 128 rows.
  - Slots that were not written hold stale rows from an earlier prompt, because `ds41_graph_reset` resets lengths, not storage. They are never read, because decode reads only the last 128 positions.
- **What stays exact.**
  - `ds41_decoder_prepare` with `publish = true` writes the decoder layers' compressed KV and indexer keys from layer 20's input for every row (`ds41_kv_source`: layers 2, 8, 14, 20; ratio 1 above layer 20).
  - Decode reads only the ring, `compressed[3]` and `index_cache[3]`, plus the last row's `residual`/`pre`.
  - Carry is prefill-internal.
- **Selections.** Layers 21-23 (and those between index sources) reuse layer 20's `selected_comp` row by row. A cut that starts at layer 21 must read the selections of the same rows, at the segment's offset.
- **Steering** projects the decoder suffix's rows in `ds41_before_attention_batch` and `ds41_decoder_prepare` (`directional-steering` spec, "Consistent enabled rounding and coverage").
- **Persistence precedent.** `ds41_steering_refuses_persistence` refuses payloads and snapshots for a steered session. The server skips `--kv-disk-dir` while steering is active (`ds4_server.c`), leaving entries untouched.

## Goals / Non-Goals

**Goals:**
- A measured ceiling before any code, and a stop if it is below resolution.
- An opt-in flag that shortens time to first token on cold prompts, with its quality cost measured and published.
- Flag off: the same bits on every path.

**Non-Goals:**
- The `mask` mode, which keeps every query and saves no time here.
- A K other than 128, or a knob for it. 128 is the window, the smallest K that fills the ring; a larger K is only worth a knob if D9 shows a quality cost the owner wants to buy back.
- Token-by-token tails, appends below the batch threshold, and decode.
- Changing the prefill schedule (`ds41_prefill_count`). The sweeps stay as they are; only the decoder part of each batched sweep shrinks.
- Making the mode default, now or by measurement. The output rule allows it only as an opt-in.

## Decisions

### D1. Measure the ceiling first
- **The runs.** Task 1.1 runs today's binary on `cold-2500`, `cold-5000` and `cold-10000`, each once, under `82GB`, with `DS4_METAL_V41_STAGE_PROFILE=1` (per-layer stage times) and `DS4_METAL_GRAPH_PREFILL_PROFILE=1` (per-layer read and map times).
- **The ceiling.** For each batched sweep and each layer from 21 to 39 (and layer 20's suffix rows above K in a wide sweep), it compares:
  - **saved compute:** the stage time scaled by `1 - K / rows`;
  - **the wall it frees:** `max(read, compute) - max(read, compute * K / rows)`.

  The read stays, because 128 rows touch about 85% of a layer's experts.
- **Projection.** The sum, divided by each shape's measured time to first token, gives the ceiling per shape. With the typical mix's prompt share, it also gives the end-to-end ceiling.
- **Stop rule.** If the ceiling is under the harness's resolution on all three shapes, the change stops and is recorded in `perf-record.md` as history.
- **Caveat.** The stage profile ends the command buffer at each stage, so its compute times run high. That only matters near the threshold, where the harness decides.

### D2. Where the cut is
- **Layers 0-20 stay as today.** Layer 20 is the first ratio-1 layer, as in DeepInfer. Its publish keeps the compressed KV exact, and its own SWA ring stays exact for the segment's rows.
  - In a wide sweep, layer 20's suffix shrinks to the segment's K rows plus today's warm rows, because only those feed layer 21.
- **Layers 21-39** run the sweep's last K rows, with `previous = 0` at the segment's first row and no warm prepare.
- **Every batched sweep is cut, not only the last.**
  - A later sweep's decoder layers start their own segment, so they never read an earlier sweep's ring.
  - A token-major tail reads the ring that the last sweep left. That ring is approximate in its first positions, and the tail goes on as decode does.
- **Skipping the earlier sweeps' decoder layers.** A sweep followed by another batched sweep could skip its decoder layers entirely, using the existing `encoder_only` route. That is S2 below, measured on its own, because its ring would then be stale rather than approximate. It is only safe when no token-major tail follows.

### D3. No kernel change
- **The window.** It follows the raw buffer's first position (Context). The only engine change is a segment start in `ds41_attention_batch`, which is `start` itself at the segment's first chunk, so `previous` becomes `min(start - segment_start, 127)`.
- **K above 2048.** A K above a chunk would still copy within the segment. K stays 128 here.
- **Confirmation.** Task 2.2 checks that the kernels see no position before s by running a synthetic segment and comparing its attention against a CPU reference that truncates at s. That test is new and model-less where the CPU reference allows.

### D4. Rows for sweeps that are not wide
- **The problem.** In a sweep of 2048 rows or fewer, every row runs through every layer from batch row 0, with no carry. The cut must make layers 21-39 operate on batch rows `N - K .. N - 1`.
- **Two ways, the smaller diff wins** (task 2.3):
  - **(a) Views at an offset.** The active `DS41_PREFILL_ROWS` views and `selected_comp` start at row `N - K`.
  - **(b) Copy down.** Copy the segment's rows to row 0 once after layer 20.

  Either way, the selections that layers 21-23 reuse must be the segment's.

### D5. Flag off is the same path
- **Code shape.** Every new branch tests one session field set only by the flag. The default path's arguments are today's: `previous` is computed as now when no segment is set.
- **The proof.**
  - `make test`;
  - the model-backed tests `tests/test_deepseek41_graph --decoder-suffix` and `make test-deepseek41-prefill-replica`;
  - parity;
  - a harness A/B with the flag off, which must be bitwise (`--bitwise`) with nothing below zero.

### D6. Persistence and steering refused
- **Persistence.**
  - A session prefilled with the flag marks itself approximate. `ds41_steering_refuses_persistence` grows into a check of either condition, with its own message.
  - The server's `kv_disk_dir` guard adds the flag.
  - Because nothing approximate is ever written, the payload ABI byte (`KV_CACHE_PAYLOAD_ABI`, header byte 20) needs no new value. Marking it would only matter if persistence were later allowed, and then a dedicated byte or flag would be designed with it.
- **Steering.** The steering numbers are judged on exact prefill, and nobody has measured how the truncated decoder rows and the steered site interact. Refusing the combination costs one check at engine open, and lifting it later is its own change. The alternative was to document the combination and allow it.

### D7. The harness's approximate mode
`ab_bench.py` gains `--approximate`:
- B's tokens may differ from A's;
- each pair records the first differing position;
- speed metrics are pooled as usual.

This is a tool step: an A/A run with it must match an A/A run without it. Without `--approximate`, a token difference still fails the run as today.

### D8. Steps and how they are judged
- **S0, tool step:** D7.
- **S1, the cut** (D2-D5). It is judged in two runs:
  - **with the flag off,** against the start commit: bitwise, nothing below zero;
  - **with the flag on** (`--b-bench-arg --approx-decoder-prefill --approximate`): the cold kinds as target, by the keep rule for the change's runtime size, and decode metrics not below zero.
- **S2, skipping the decoder in sweeps followed by another sweep.** Judged on `cold-10000`, flag on, against S1.
- **Prefill and GPU sections.** If S1's predicted end-to-end effect is under the harness's resolution while the ceiling passed, the config's section-time rule applies. `ab_bench.py --sections` already exists.

### D9. Quality, so the owner knows the price
With the flag on against off, all quality runs under streaming with the largest admitted cache:
- **Parity prompts:** first-token agreement, and the first differing position per prompt, greedy at 512 tokens.
- **`./sf-ds4-1flash-eval --suite core`:** scores side by side.
- **Long context:** `test_long_story_fact_recall` through `DS4_TEST_LONG_PROMPT`, and one 10K-token retrieval prompt whose answer sits more than 128 tokens before the end.
- **Logits:** the first token's KL divergence and top-1 agreement on 20 prompts.

The numbers go into `README.md`'s flag section and the `AGENTS.md` row. No steering or eval run in this change uses the flag.

## Risks / Trade-offs

- **[The ceiling is small because reads dominate]** → D1 stops the change before any code is written.
- **[Quality loss shows up only on long-range retrieval]** → D9's retrieval prompt puts the answer outside the last 128 tokens. Only the decoder layers' SWA is approximate; their compressed KV covers the whole prompt exactly.
- **[A stale ring slot is read]** → Decode reads only the last 128 positions, all written by the segment when K ≥ 128. Task 2.2 adds a check that fills the ring with a sentinel before a compact prefill and asserts no sentinel reaches attention.
- **[Selections misaligned in layers 21-23]** → D4's offset applies to `selected_comp` as well. A wrong offset shows as a large first-token divergence in D9, and is checked directly by comparing the indices that layers 21-23 read against layer 20's for the segment.
- **[Approximate state leaks into a later exact session]** → Persistence is refused (D6). The in-process server keeps live sessions under the same process-wide flag, so a session never mixes modes.
- **[`320` brings speculative verify]** → DeepInfer requires K ≥ window + back-tracking tokens. If `320` lands, K must be at least 128 + the draft block. This is noted in `320`'s risks when either change lands.
