# What We Know About DeepSeek V4.1 Flash

[README](../README.md)

This page collects what this repository knows about the model it runs: how the
network is built, what each layer does, what it costs on this machine, how it
can be driven and observed, and what has never been measured. It is a reference
for deciding how to use the model, not a user guide. Each fact names its
source; "code" means `ds4.c` at the line given, as of the commit that last
touched this page.

Three kinds of statement appear here and are kept apart:
- **from code**: what the implementation does, read from the source;
- **measured**: a number from a recorded run, with the file that holds it;
- **unknown**: listed in [Known unknowns](#known-unknowns), never estimated.

Performance numbers are from one Apple M5 Max with 128 GB, Q2 GGUF `1017`,
SSD streaming, as everywhere in this repository.

## Architecture

### Dimensions (from code, `DS4_SHAPE_FLASH41`, `ds4.c:243`)

| | |
|---|---|
| Layers | 40 |
| Width (`d_model`) | 5120 |
| Vocabulary | 129280 |
| Attention | 64 query heads, 1 KV head; key and value are the same 512-dim latent row |
| RoPE | 64 of the 512 dims; theta 10000 on layers 0-1, 160000 on 2-39; YaRN factor 16 over an original 65536 |
| Query path | low rank: 5120 → 1280 → 64×512 |
| Output projection | 8 groups of 4096 → 1024, then 8192 → 5120 |
| Experts | 384 routed, 6 used per token, 1 shared; FFN width 2304, SwiGLU clamped at 10, routed weights scaled by 1.5 |
| Sliding window | 128 raw rows per layer |
| Indexer | 32 heads × 128 dims, top 512 compressed rows |
| Residual | 4 hyper-connection (HC) streams of 5120, mixed by a Sinkhorn-normalised 4×4 matrix (20 iterations) |
| Context | `max_position_embeddings` must be 1048576 |
| Draft heads | none: `n_nextn_predict` is 0, so no MTP and no speculative decoding |

There are no dense leading layers and no hash-routed layers. The GGUF must
declare `scoring_func=sqrtsoftplus`, `topk_method=noaux_tc` and
`norm_topk_prob=true` (`config_validate_deepseek41_model`, `ds4.c:3889`).

### Layer map (from code, `ds4.c:640-664`)

| Layers | KV compression | Owns compressed KV | Runs the indexer | Engram |
|---|---|---|---|---|
| 0 | none: sees only the last 128 tokens | | | |
| 1 | none: sees only the last 128 tokens | | | yes |
| 2-19 | 2 tokens per row | 2, 8, 14 (each serves itself and the next five) | 2, 8, 14 | 14 |
| 20-39 | 1 token per row | 20 (serves 20-39) | 20, 24, 28, 32, 36 | |

A layer that does not run the indexer reuses the previous index layer's
selection. Above 2048 candidate blocks (more than 16384 compressed rows),
layer 20 also keeps a mask of its best 2048 blocks of 8 rows, and the later
index layers score only those (`ds4.c:23862`).

### One decode token, in order (from code, `ds41_graph_step`, `ds4.c:24553`)

1. **Embedding.** The F16 embedding row is written into all four HC streams.
   The token is hashed for Engram on the CPU, and the rows are read on worker
   threads while the first layers run.
2. **Engram** (layers 1 and 14, text positions only). Up to the last four
   tokens, through a compressed vocabulary of 99092 ids, form 2-, 3- and
   4-grams. Each n-gram is hashed into 8 prime-sized tables: 24 rows of
   256 E4M3 bytes per token and layer, about 384 million rows per layer and
   189 GiB in all, read from disk with uncached `pread`. The 24 rows (6144
   dims) project to four keys, one per stream, and one value. Each stream
   adds the value through a sigmoid gate on its similarity to its key
   (`ds4_engram.c:38`, `metal/dsv41.metal:283`).
3. **HC attention input.** The four streams are RMS-normed and mixed into one
   5120 row, rounded to BF16 (`ds41_hc_mix`, `ds4.c:23743`). The same step
   computes the weights that will spread the block's output back over the
   streams. Steering acts on this row ([Steering](#steering)), then
   `attn_norm`.
4. **Projections.** Query 5120 → 1280 → 64×512 with RoPE; one KV row 5120 →
   512.
5. **Raw window.** The KV row is roped, stored as FP8 E4M3 in this layer's
   128-row ring.
6. **Compressed KV** (layers 2, 8, 14, 20). A compressor writes one 512-dim
   row per 2 tokens (layers 2-19) or per token (layer 20), stored as FP4. The
   same step stores a 128-dim FP4 index key.
7. **Indexer** (index layers). 32 index heads score every compressed row,
   weighted per head, and keep the top 512 (`metal/dsv4_misc.metal:770`).
8. **Attention.** Each of the 64 heads attends over up to 128 raw rows and the
   512 selected compressed rows, with a learned per-head sink.
9. **Output.** The grouped output projection, then an HC expand back into the
   four streams.
10. **HC FFN input**, the same mixer with its own weights, then `ffn_norm`.
11. **MoE.** The router (F32, 5120 → 384) gives p = sqrt(softplus(logit)). The
    top 6 are ranked by p plus a learned bias (a separate bias at image
    positions); the weights are p normalised to sum 1, times 1.5. The six
    routed experts and the shared expert are summed and expanded into the
    streams (`ds41_moe_partial`, `ds4.c:24018`).

After layer 39 the streams are folded once more, normed, and multiplied by
the 5120 → 129280 output head (`ds41_graph_logits`, `ds4.c:24100`).

### Encoder and decoder halves

The code calls layers 0-19 the encoder and 20-39 the decoder. Layers 21-39
read only layer 20's compressed keys, published for the whole prompt, and
their own 128-row windows. So the last token at layer 39 depends on 127
earlier inputs, layer 38 on 254, and layer 20 on 1 + 20 × 127 = 2541 rows
(`ds41_decoder_prepare`, `ds4.c:24844`). A prompt prefill runs layers 0-19
over every row, lets layer 20 publish keys for every row, and computes the
decoder only on that shrinking tail. Prompts under 2541 rows do not take this
shortcut.

### Precision (from code, `ds4.c:3760-3840`, `ds4_deepseek41_gpu.h`)

- Routed experts: gate and up IQ2_XXS, down Q2_K (one expert 9.49 MiB).
- Output projections Q8_0; embedding, HC mixers, compressor, indexer and
  Engram projection F16; router, norms, sinks and biases F32.
- Activations between blocks are BF16. Raw KV is FP8 E4M3, compressed KV and
  index keys FP4 E2M1, each with per-group scales.
- Decode reads exact narrow copies of the router (BF16) and of the Engram and
  indexer projections (E4M3).

## Prompt format and reasoning effort

From code (`ds4.c:27218-27275`): BOS, then an optional `<｜System｜>` turn,
then `<｜User｜>`, then `<｜Assistant｜>` followed by `<think>` when thinking
is on or `</think>` when it is off. Reasoning effort is only text: the system
turn gets the line `Reasoning Effort: N (range 1-100, the higher the value,
the more thorough the reasoning)`. Level 0 omits the line and closes thinking.
Tool calls are DSML blocks; tool results come back as a user turn wrapped in
`<tool_result>`.

Request names: `none`/`minimal` 0, `low` 25, `medium` 50, `high` 75 (the
default), `xhigh` 90, `max` 100, or a number
(`openspec/specs/reasoning-effort/spec.md`).

Measured unsteered think length, 20 benign prompts, budget 8192
(`com-steering/investigation.md`, 419 calibration):

| Level | Median tokens | p90 | Hit the budget |
|---|---:|---:|---:|
| 10 | 1243 | 3627 | 1/20 |
| 25 | 593 | 2577 | 0/20 |
| 50 | 753 | 2687 | 1/20 |
| 75 | 1161 | 3184 | 1/20 |
| 100 | 2188 | 4754 | 5/20 |

Length is not monotonic in the level, and a low level is not short. On 20
harmful prompts the model closed its reasoning after 121-430 tokens. No
measurement relates the level to answer quality.

## Cost on this machine

### Decode (measured)

- Rested machine, `80GB` cache: 30.9 t/s at 2K context, 31.9 at 8K, 30.2 at
  32K, about 32 ms per token (README, "Against ds4"). Under sustained load
  (thermal pressure Heavy) about 24 t/s.
- 40K and 72K: 31.4 and 31.2 t/s; about 246K: 29.7 t/s
  (`speed-bench/perf-record.md`, `690` and `760`).
- A token reads 6 of 384 experts in each of 40 layers, 2.22 GiB of routed
  weights. The expert cache hits about 98%; 3.9-4.4 layers per token miss
  one expert, about 2.7 ms (7%) of the token. Engram waits are 0.02-0.05 ms.
- Each layer is three GPU batches: router about 390 µs, shared expert
  about 50 µs, routed experts and the rest about 199 µs. The GPU is busy 86%
  of the token (perf-record, "Decode submission after 120").

### Routing locality (measured, perf-record "Situation 0", "Memory levers")

- 5000 prompt + 2000 generated tokens touched 11088 of the 15360
  (layer, expert) pairs, against about 8000 cache slots.
- The previous layer's router input predicts 70% of a layer's selections in
  its top 6, but only 24% of the misses: misses are the unpredictable
  experts.
- Right after a wide prefill sweep the per-layer hit rate falls to 0.33-0.54.

### Prefill (from code `ds41_prefill_count`, measured in perf-record `770`)

| Prompt or append | How it runs | Cost |
|---|---|---|
| under 256 tokens | token by token, decode kernels | about 31 ms per token |
| 256 to about 2000 | one SSD layer sweep | 6.0-7.0 s, almost independent of length |
| longer | wide sweeps of 2048-row tiles, decoder on a tail | first 2048 at 181 t/s, later at 238-704 t/s |

Break-even between the two is about 200 tokens. Measured appends: 64 tokens
2.0 s, 128 tokens 4.2 s, 256 tokens 6.5 s, 1000 tokens 7.0 s.

Time to first token, rested machine (README):

| Prompt | Prefill |
|---|---:|
| 512, first prefill of a fresh process | 10.8-12.0 s |
| +512 append | 6.0-6.9 s |
| 2500 | 11.5 s |
| 5000 | 12.2 s |
| 10000 | 21.0 s |

The first generated token costs 0.11-0.22 s after a sweep and 0.03-0.04 s
after token-by-token rows.

### Start-up and small requests (measured)

- Engine open: 2.3-2.8 s with the static weights in the file cache, 4.3 s
  cold.
- A process's first prefill costs about 4.5 s more than later ones, once per
  process; the cause is not established.
- Disk KV checkpoints: 23-49 MiB per request, stored in 16-22 ms and loaded
  in 10-16 ms. The end-to-end saving of a cache hit has never been isolated.
- Under SSD streaming the server does not batch sessions: N sessions decode
  one after another (`ds41_sessions_batch_supported`; docs/SERVER.md,
  "Ordered fallback").

### Memory (measured)

Static weights 9.37 GiB, read by every token and locked. Expert cache 72.40
GiB (7810 slots) at `80GB`. Prefill reserve 7.12 GiB. Context buffers 7.89 GiB
at 32K, 10.38 at 256K. Free memory sits under 1 GiB; the file cache is the
only headroom. Details in `AGENTS.md`, "SSD streaming is not optional".

## Determinism

- The same request on the same build gives the same tokens and logits, and
  the same expert misses.
- **The prefill schedule decides the output.** Batched and token-by-token
  kernels round differently, so the same text sent as one prompt or as
  appends of different sizes can produce different, equally valid outputs.
  Change `770` moved logits by up to 1.37 and diverged 16 greedy tokens.
- Greedy output is token-identical to upstream ds4 on the parity prompts.
- Steering evaluations saw about 3 of 44 judged labels flip between identical
  runs (`com-steering/kpi.md`); the cause is not established.

## Quality (measured)

Teacher-forced scoring against the DeepSeek API's own continuations
(`QA_BEFORE_RELEASES.md`, §11):

| Model and execution | Mean NLL | Top-token agreement with the API |
|---|---:|---:|
| Q2, M5, SSD streaming | 0.3646 | 90.1% |
| Q2, Metal TP | 0.3615 | 90.1% |
| Q4, M5, SSD streaming | 0.2465 | 96.7% |
| Q2 resident, 64K/96K | 0.559 | 85.2% |

The fixtures date from September 2026 (reference revision `df42c10`); no
score on the `1017` GGUF is recorded. `sf-ds4-1flash-eval` has suites
(`core` 92 cases, `hard` 50; `EVAL_DATA.md`), but no recorded scores.

## Steering

What the steering work established, with aggregate numbers only
(`com-steering/`, `dir-steering/README.md`):

- **Site.** The HC attention input of layers 1-39, after Engram and before
  `attn_norm`: `h -= F·d·⟨d,h⟩` with one 5120 direction per layer, up to two
  directions, each gated to the think or the answer phase. FFN and attention
  sites are refused on V4.1.
- **What sits where.** Masking layer ranges showed that compliance is carried
  by layers 30-39, and that the suppression of `</think>` under steering sits
  in layers 1-9.
- **Leaving the reasoning.** In the base model `</think>` is a cliff: its
  logit gap is about 22 ten tokens before the exit and 0 at it. A steered
  model keeps the gap flat near 20, so the decision to stop is absent; an
  additive "closure" direction (just before a natural `</think>` minus
  mid-reasoning) restores it.
- **Divergence.** A steered answer leaves the base model's at token 0-5
  (median 3).
- **Scale.** A factor of about 7 works best for the shipped directions.
  Decode was 12% slower steered on 2026-10-13; not re-measured since.
- **Dead ends.** A "harmful content" direction found by LDA was not the
  refusal direction. Per-prompt routing of profiles never beat a fixed one.
  A controller driven by a layer-25 projection did worse.

Benign behaviour, over-refusal and capability under the shipped profile are
unmeasured.

## Driving and observing the model

### Server (`docs/SERVER.md`, `ds4_server.c`)

- Endpoints: `/v1/chat/completions`, `/v1/responses`, `/v1/messages`
  (Anthropic), `/v1/completions`, `/v1/models`, `/v1/systemone` (typed
  decisions, change `810`).
- `/v1/completions` is not raw completion: it wraps the prompt in the chat
  template with the system message "You are a helpful assistant"
  (`ds4_server.c:5214`).
- Accepted: `temperature` (≤ 0 is argmax), `top_p`, `min_p`, `top_k`,
  `seed`, `stop`, `max_tokens`, `stream`, `ignore_eos`, tools,
  `reasoning_effort`, images with `--vision`.
- Ignored without error: `logprobs`, `top_logprobs`, `response_format`,
  JSON schema, grammar, `logit_bias`. `tool_choice` honours only `"none"`.
  An assistant prefill is closed, not continued.
- Reuse: the live session's prefix, and a disk KV cache (`--kv-disk-dir`).
  A history that does not extend the live prefix exactly is prefilled again.

### Logits, routes, hidden states

| What | Where | State |
|---|---|---|
| Next-token logits, top-k logprobs | C API: `ds4_session_copy_logits`, `ds4_session_top_logprobs`, `ds4_session_token_logprob` (`ds4.h`) | available |
| Logits to a file | CLI `--dump-logits`, `--dump-logprobs`; bench `--dump-frontier-logits-dir`; `DS4_GLM_LOGIT_DUMP` | available, one process per dump |
| Logits over HTTP | `POST /v1/systemone` with `"sf":{"debug":true}`: the option symbols' raw logits only | available for option symbols; no general logprobs |
| Selected expert ids | `DS4_MOE_RECORD_SELECTED_IDS` writes 6 ids per entry, without a layer tag; the ids reach the CPU every decode token anyway (router readback) | recorder not verified on V4.1; no API |
| Hidden states, per-layer tensors | `DS4_METAL_GRAPH_DUMP_*`, `ds4_session_eval_layer_slice` | generic-graph code the V4.1 graph never calls: not available |
| Steering-site rows | — | the capture used by the steering work was removed |

## Known unknowns

Architecture:
- the actual quantization types of the query, KV, shared-expert and output
  tensors in `1017` (only the allowed set is checked);
- whether training grouped the experts (`noaux_tc`); the kernel ranks all 384;
- why the HC fold uses the previous block's split weights (implemented and
  commented, not explained).

Cost:
- time to first token of a fresh prompt under 256 tokens on the current tree;
- a short turn on a cached system prefix through the server, end to end;
- latency distribution (p50, p99) over many short chat requests (a decision
  read from logits: `sysone-bench/record.md`);
- throughput with several concurrent sessions under streaming;
- whether the expert cache stays warm across many unrelated short prompts;
- HTTP and template overhead;
- the cost of thinking at each level, and of sampling against greedy.

Behaviour:
- any quality score on `1017`, and eval suite scores;
- the effect of the reasoning level on answer quality;
- calibration of the output probabilities in chat (for typed decisions read
  from logits: `sysone-bench/record.md`, ECE 0.23 raw, 0.04 calibrated);
- the steered model on benign tasks;
- the cause of the cross-run label flips and of the first-prefill cost.

Interfaces that do not exist:
- logprobs over HTTP, constrained decoding (grammar, JSON schema,
  `logit_bias`), forced tool choice, assistant prefill;
- an embeddings endpoint, early exit (typed decisions read from logits now
  exist: `sf_sysone.h`, change `800`, `docs/system-one.md` "Template");
- hidden-state or per-layer readout on the V4.1 graph.
