# System One: decision models, and what applies to this model

[README](../README.md) · [What we know about the model](MODEL_KNOWLEDGE.md)

A "System One" model answers *typed questions* about a *state* with
probabilities and generates no text. This page records what the public systems
do (read 2026-11-11), the wire API they share, and which of their techniques
can work for DeepSeek V4.1 Flash under SSD streaming on one Mac. The changes
`800`-`930` in `openspec/changes/` build on it; each names the section it uses.

Nothing on this page was measured here. Numbers about other systems are their
authors' claims.

## 1. The systems

| System | Kind | How it collapses to an answer | Source |
|---|---|---|---|
| **Jev** (TypeSafe AI, 2026-09-15) | hosted, closed weights | not disclosed; "non-autoregressive", 70-500 ms, output free | docs.typesafe.ai |
| **Laya** (Convai Innovations) | open, 322-421M encoder | **added layers**: ModernBERT/mmBERT encoder + a decision head trained from scratch (2 transformer layers, an option-marker scorer). One `[MASK]` per option, logit read at each marker, softmax per question. 512-8192 tokens | huggingface.co/convaiinnovations/laya |
| **JevK5** (allebee) | open, Qwen3.5-4B/9B + merged LoRA r16 | **no added layer**: options get letters, softmax over the letters' next-token logits, one temperature. Max 16 options per pass, more by grouped passes plus a "knockout" pass. 16384 tokens max | github.com/allebee/jevk5 |
| **Rizzo Flow** (Rizzo AI Academy) | open, llama.cpp, Spark-X2.5 4B/1.7B + LoRA | **no added layer, prefill only**: state first, prefilled once; each question is a suffix branch sharing the state's KV; read the letters' logits at one position; nothing sampled | github.com/Rizzo-AI-Academy/rizzo-flow |
| **CLM-8B** (Contrastive-LM, 2026-09-23) | open, frozen Qwen3-8B + two trained heads (about 20M parameters) | **added heads, no option in the prompt**: last-token row of the state → state head; each option text → action head; answer = softmax of scaled cosine; option vectors cached. `clm-raw` ablation: cosine in the raw encoder space, no accuracy published | github.com/Contrastive-LM/CLM |
| **LLM-as-Jev** (arXiv 2610.02076) | paper | shows a plain causal LLM is already a decision model *without training*: numeric ids `[k]`, score each id's token path by teacher forcing from one shared prefill | arxiv.org/abs/2610.02076 |

Four families, then (the fourth is CLM's: a frozen LLM as encoder, trained
projection heads, a dot product; section 5):

1. **Encoder + trained head** (Laya). Fast and small; near chance zero-shot on
   new schemas until fine-tuned (its card: 0.36 base against 0.77 fine-tuned).
2. **Causal LLM + logit readout** (JevK5, Rizzo Flow, LLM-as-Jev). The model is
   unchanged or lightly tuned; the "answer layer" is the model's own output
   head, read at one position and restricted to the option tokens.
3. **Unknown** (Jev).

### What each one teaches

**Rizzo Flow** (the closest to what this repository can do):
- Layout: state at the start of the prompt, processed once; each question a
  suffix; branches share the state's KV cells; default micro-batch 4.
- Each option is one uppercase letter, checked at request time to be exactly
  one token in context: at most 26 options.
- Abstention as built-in options (`__insufficient__`, `__below_range__`,
  `__above_range__`); its README says the model picks abstention almost always
  when enabled, or never when evidence is missing: unreliable either way.
- Per-primitive temperature scaling, fitted offline, bound to a fingerprint of
  weights, precision, runtime and prompt version.
- Documented limits: uncalibrated by default; residual position bias (no
  permutation debiasing); 26 options; shared-prefix scoring at Q8 flipped
  13 of 777 near-ties against direct scoring; requests serialized.
- It serves two APIs: its own `/v1/decisions` and Jev's `/v1/systemone`.

**JevK5**: letters and one temperature (1.22 for 4B); more than 16 options
cost `ceil(n/16) + 1` passes; training was cross-entropy on the letter logits
from a teacher that answered twice and kept agreeing answers; English only.

**LLM-as-Jev** (the most useful result for a model nobody can fine-tune):
- Prompt: default chat template, **thinking off**; user message with a
  `State:` line and an `Options:` list of `[k] option` lines, then "Select one
  option. Answer only with its bracketed numeric identifier."; the assistant
  turn is **prefilled** with `Best answer: [`.
- Candidate k is the continuation `k]`. Every continuation ends in `]`, so
  none is a prefix of another and the option count is unbounded. The score is
  the sum of the token log-probabilities along the path, softmax over
  candidates. 151 classes cost one prefill and at most three short passes.
- Training-free scoring on a 4B model equals its own greedy generation on all
  231 benchmark items, and beat the fine-tuned open alternatives. LoRA added
  2.6 points; full fine-tuning added nothing. A 0.6B model needs fine-tuning.
- Failure modes: left-to-right position bias; intent-only tuning creates a
  yes-bias and suppresses "none of the above"; small models put little
  probability on legal tokens (measure the *legal mass*).
- It ran no early-exit, layer-truncation or thinking experiment.

**Laya**: per-(type, option count) temperature cut ECE from 0.47 to 0.08, so
calibration must be fitted, not assumed; `noul` followed its `true:`/`false:`
labels instead of the state (use neutral option keys); the act/escalate head
carried no signal, while plain confidence did (AUROC 0.77).

## 2. The standard wire API (TypeSafe `POST /v1/systemone`)

Laya, JevK5 and Rizzo Flow all serve this shape, so it is the de facto
standard. Source: docs.typesafe.ai/api/system-one, /api/errors, /confidence;
canonical spec `https://api.typesafe.ai/openapi.json`.

### Request

`POST /v1/systemone`, `Authorization: Bearer <key>`, `application/json`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `model` | string | yes | model name or alias (`jev-latest`); names come from `GET /v1/models` |
| `state` | string, object or array | yes | the content every question refers to |
| `questions` | object | yes | at least one; keys are caller-chosen names, values are question objects |
| `assets` | object | no | images: `{type:"image", format, data_base64}`; referenced by placeholder |

Question objects (all have `type`; `instructions` is string, object, array or null):

| `type` | Extra fields | Answer fields |
|---|---|---|
| `noul` | `criteria` optional: `{ "true": ..., "false": ... }` | `noul`: number 0-1, probability of yes |
| `choice` | `criteria` required: object, 1-255 option names → description (string, object, array or null; null = judged by name) | `choice` (top name), `confidence`, `probabilities` (name → p) |
| `score` | `criteria` required: array of 1-10 level descriptions, position is the score from 0 | `score` (probability-weighted mean), `confidence`, `legend` (`"0"`.. → text), `probabilities` (`"0"`.. → p) |
| `box` | needs an image | `box` `{top,bottom,left,right}` fractions, `confidence` |

Every answer also repeats `type`. Questions are evaluated "in parallel and in
isolation against the same state": one question must not see another.

### Response (200)

```json
{ "model": "<name>", "answers": { "<question name>": { "type": "...", ... } },
  "usage": { "input_tokens": 123, "output_tokens": 0 } }
```

`GET /v1/models` → `{ "models": [ { "name", "description", "release_date" } ] }`.

### Confidence (how concentrated, not how correct)

- `choice`, n options, top probability p: `(p − 1/n) / (1 − 1/n)`.
- `score`, n levels, m the most likely level:
  `max(0, 1 − Σ pᵢ·|i − m| / MAD)` with `MAD = (1/n) Σ |i − (n−1)/2|`.
  Check: (0, 0.57, 0.43) gives about 0.35.
- `noul` has no field; callers use `|2p − 1|`.

### Rules and errors

Body at most 32 MiB, UTF-8 without BOM, nesting at most 64 levels in `state`,
`instructions`, `criteria`; finite numbers only.

| Status | When |
|---|---|
| 400 | a request rule broken; `max_tokens_exceeded` when the input exceeds the context |
| 401 | missing or wrong key |
| 413 | body above 32 MiB |
| 422 | validation: `detail` is a list of `{loc, msg, type}` |
| 429 / 529 | rate limit / overloaded |

## 3. What this model changes

Facts from [MODEL_KNOWLEDGE.md](MODEL_KNOWLEDGE.md) that decide the design:

| Fact | Consequence |
|---|---|
| A token costs about 31 ms; a layer sweep costs 6-7 s whatever its length (256-2000 rows); under 256 rows the prompt runs token by token | A decision can never cost 50 ms here. The cost is `state prefill + 31 ms × question tokens`. **Every token of a question suffix is money**: the designs below shrink the suffix, not the readout |
| Sessions are not batched under SSD streaming (`ds41_sessions_batch_supported`) | Rizzo's micro-batch of question branches is unavailable. Branches run one after another from a snapshot |
| `ds4_session_rewind` invalidates the checkpoint (compressors cannot be truncated) | A branch needs `ds4_session_save_snapshot` / `ds4_session_load_snapshot`. The payload is 23-49 MiB at chat sizes and already holds the logits |
| The token-major prefill tail computes no logits until the last row | Only the readout position pays the 5120 → 129280 head |
| 340 GiB of Q2 weights, no training stack | No LoRA, no fine-tune. Everything is training-free, or trains a tiny readout *outside* the model on captured rows |
| Layers 0-19 "encoder", 20-39 "decoder"; a layer at position t reads only lower layers | A readout taken at layer L never needs layers above L, for any token: an early exit saves `(40 − L)/40` of both prefill and suffix. Whether a useful answer exists at L < 40 is unmeasured |
| Steering computes `⟨d, h⟩` on the attention-input row of every layer | A linear probe on a hidden row is nearly free at run time; the capture that would train one was removed and must come back |
| Thinking can run for thousands of tokens; `</think>` is a token | A bounded think followed by a forced `</think>` and a readout is a cheap middle ground no surveyed system has |
| Context to 1M tokens, Italian and other languages, vision | The reasons to do this on a large local model at all: long states, non-English states, private data, and a strong zero-shot reader |

### Approaches, by family

| # | Approach | Change | Standing |
|---|---|---|---|
| A | Logit readout on letter tokens, state first, branch per question by snapshot | `800` | the base; everything else is measured against it |
| B | Jev wire API over HTTP | `810` | makes every existing Jev client and benchmark usable |
| C | Bench: accuracy, calibration, latency; the model's own thinking answer as teacher | `820` | the instrument; no later change is accepted without it |
| D | State cache across requests; preserve the chat session around a decision | `830` | turns the 6-7 s state prefill into a one-time cost |
| E | **Schema-first layout**: question definitions before the state, a 4-8 token pointer suffix per question; **prior correction** read once per schema | `840` | new here; cuts the per-question cost about tenfold; breaks strict isolation, so opt-in |
| F | Numeric id trie for 27-255 options | `850` | from LLM-as-Jev; options are listed once, extra depth costs one token per live branch |
| G | **Bounded think**: N reasoning tokens, forced `</think>`, readout; think once, answer many | `860` | new here; an accuracy/latency dial, started only if `820` shows a gap |
| H | **Early exit**: readout at layer L through the model's own head (logit lens), or a self-distilled translator or linear probe; then never run layers above L | `870` | research with stage gates; the owner doubts layers can go, and so does this page until measured |
| I | **Conversation as state**: a decision on the chat the slot already holds, asked as a next user turn | `835` | new here; the state prefill is already paid |
| J | **Fitted prior strength**: contextual calibration, CAD and CFG are one formula on option logits; fit its factor instead of assuming 1 | `845` | free per request; kept only if it helps |
| K | **Layer screen from snapshots**: per-layer rows at the readout position, with no engine edit; centroid probe and similarity readout (CLM-raw) for every layer | `865` | answers "which layer" and the CLM question before `870` edits anything |
| L | **Indexer scores as evidence**: the model's trained per-row relevance score, read at the decision | `890` | new here; a probe with a kill rule |
| M | **Branch cost**: time snapshot save, restores and suffix evaluation per question | `805` | added after `800` measured 2.4-3.7 s per decision that the suffix tokens do not explain |
| N | **Suffix diet**: tokenize the suffix as one string and drop fixed text, gated on the bench | `815` | about 0.3 s per question on the default layout if ten tokens go |
| O | **Injection probe**: special-token text in a state, and instructions inside a state that try to pick the answer | `855` | a security check before anyone automates on the endpoint |
| P | **Confidence escalation**: bounded thinking only for questions under a calibrated threshold | `862` | `860`'s gain for a fraction of its cost; needs `860` kept |

Considered and not proposed:

- **LoRA or any fine-tune of the model** (JevK5, Rizzo): no training stack for
  a 340 GiB quantized model on this machine.
- **A trained encoder head à la Laya**: it is another model, not this one.
  Laya itself could run beside the server as a cascade (Laya first, this
  model when Laya's confidence is low); that is a client-side pattern and
  needs no code here.
- **Micro-batched branches**: needs multi-session batching under streaming,
  which the engine refuses; the gain would come only from sharing expert
  reads, and decode already hits the cache 98% of the time.
- **One sweep over all question suffixes with per-question attention masks**:
  the batched kernels have no per-row visibility mask, the compressed KV and
  the indexer would need one too, and a sweep costs 6 s. Not worth a kernel.
- **Expert routing as a feature vector** (the six expert ids per layer reach
  the CPU every token): attractive because it is free, but it needs a labelled
  set per task and a trained classifier; revisit only if `870` shows hidden
  rows carry the answer early.
- **Permutation debiasing by re-running each question with shuffled options**:
  doubles the suffix cost. `840`'s prior correction attacks the same bias for
  one extra readout per schema; `820` measures whether either is needed.
- **Abstention as a built-in option**: Rizzo's own data shows it is unreliable.
  Callers add an explicit option to `criteria` when they want one.
- **`box`**: needs coordinate regression; answered with 422.

## 5. Second round: model-specific ideas, each checked against the code

Two read-only explorations (2026-11-11) proposed ideas from this model's own
mechanisms and had each one attacked by independent reviewers reading
`ds4.c`. Nothing was run. What they established:

**A defect in the first draft of `870`.** Ending the layer loop early is not
enough: the output head folds the four residual streams with weights that
only the last layer hands over, so an early exit would have read one stream
of four. Four reviewers found it independently; `870` now carries a fourth
edit.

**CLM cannot be reproduced on one Mac, and most of its speed does not
transfer.** Its heads are trained on about 90M pairs; one day here yields a
few thousand decisions, enough for class centroids and a temperature. Its
latency comes from one pass of an 8B encoder; here the state pass dominates
and is the same for a similarity readout and a logit readout, and `840`
already caches the option text. The useful reading of CLM for this model:

- the `800` readout **is** a contrastive readout: the state vector is the
  final normed row and the "action head" is the model's own output matrix,
  trained on far more data than CLM's heads;
- a separate similarity readout matters only if it works **below layer 40**
  or **without the options in the prompt**. `865` measures both, per layer,
  with no engine edit;
- expectations from the literature on untrained embeddings of causal LLMs:
  intermediate layers are as good as or better than the last one (the one
  point in favour of "up to some layers"); on `choice` a similarity readout
  should land 10-25 points under the logit readout, near parity only on
  intent or topic sets; `noul` and `score` should stay on the logit readout.

**The model has its own trained contrastive lookup.** The indexer scores
every row of the context against the current position at eight layers. `890`
probes it as evidence for a decision.

**Contrast between logits moves quality, never latency.** With-state against
without-state is one family with one free factor (`845`). Final layer against
an earlier layer (DoLa) is an offline table in `870`; published results on
multiple choice are flat.

Verified as feasible and written as changes **for senior implementers**
(`900`-`930`); each proposal states its level at the top:

| Idea | Change | What it would buy | Why it is not routine |
|---|---|---|---|
| **Fork sweep**: K question branches inside one layer sweep, each isolated by saving and restoring its rows after layers 2, 8, 14, 20 | `920` | K answers for about one sweep (6-7 s) with strict isolation, instead of K suffixes | a new sibling of the prefill sweep in `ds4.c`, large; bitwise test mandatory |
| **State capsules**: encode segments separately and splice their compressed rows at the payload level in fixed padded slots | `910` | recombination of N documents × M schemas without N × M prefills | approximate by construction (only the first slot is exact); quality unmeasured; dense-model literature predicts a loss on cross-segment reasoning |
| **All layers in one pass**: the head applied after every layer on the readout token | `900` | the whole per-layer table from one normal run, on swept states | 30-40 lines, a drain per layer, a trigger from the sync loop; cannot produce `870`'s timing column |
| **Selection knockout**: mask a span out of the indexer's candidates and watch the answer move | `930` | a causal check of an evidence span | only a positive shift is interpretable; a research probe at most |

Checked and rejected:

- **Pre-seeding the expert cache for the question suffix**: at most 0.1-0.2 s
  on a 6-7 s decision, and shrinking the popularity seed slows the next
  sweep, which the repository already measured.
- **Router near-ties as a fragility signal**: 40 routing decisions out of
  tens of thousands; the top-two logit gap against a measured `delta95`
  does the same job with no engine code (`820`).
- **Attention-mass abstention** (sink, window and compressed shares): a
  kernel-level readback for a failure nobody has measured here; `820` first
  measures what an explicit option and a companion `noul` achieve.
- **Decision taps during generation**: mid-reasoning the stop signal is a
  cliff, so free taps say almost nothing; `835` keeps only the tap between
  turns.
- **Convergence-based early stop of thinking**: published (Dynasor-CoT,
  DEER); `860`'s trajectory run shows whether it would pay here.
- **Trained CLM heads, or a small student model taught by this one**: needs a
  training stack this machine does not have and data it cannot produce in
  useful time.

Not verified (ranked below the cut): a refusal-direction check on sensitive
states, a routing-fingerprint novelty score, a training-free image `box`
from index scores over image rows, the closure direction as a soft landing
for bounded thinking.

## 6. Vocabulary used by the changes

- **state prefix**: BOS, system turn, user marker and the state text. Shared
  by all questions of a request.
- **question suffix**: the question text, options, the assistant marker,
  `</think>`, and the answer prefill. Evaluated once per question.
- **readout**: the next-token logits at the last suffix position, restricted
  to the option tokens.
- **legal mass**: the probability the full softmax puts on option tokens. Low
  legal mass means the prompt format failed, whatever the winner.
- **branch**: restore the state snapshot, evaluate one suffix, read out.

## 7. Template (measured, change `800`)

`sf_sysone.h` / `sf_sysone.c` implement the readout with the public `ds4.h`
API only. The answer layout was chosen by `tests/test_sysone MODEL --probe`
on the 1017 Q2 GGUF (SSD streaming, 32 GiB expert cache, ctx 4096,
2026-11-11), over the 12 fixtures of the `800` design:

| Id | Prefill | Correct | Mean legal mass | Min legal mass |
|---|---|---|---|---|
| T-A | `Best answer: [` | 12/12 | 0.9999 | 0.9995 |
| T-B | `[` | 12/12 | 0.1682 | 0.0000 |
| T-C | (none, read after `</think>`) | 12/12 | 1.0000 | 0.9997 |

T-A and T-C tie on correct fixtures; T-C has the higher mean legal mass and
is frozen as template version 1. T-B's mass is near zero because after a bare
`[` the model writes the bracketed option token (`[A` is one token in the
option lines), not the bare letter the readout reads.

Frozen layout (each piece tokenized on its own, never as one string):

```text
<BOS><System>You are a decision function. Read the state and answer the question by choosing exactly one of the listed options.
<User>State:\n{state}                                  <- state prefix ends here
\n\nQuestion: {instructions}\nOptions:\n
A. {name}[: {text}]\n ...                            (noul: A. Yes / B. No; score: 0. {level} ...)
Answer with the identifier only.<Assistant></think>   <- option-symbol logits read here
```

Measured by `make test-sysone` (same settings; three questions of 28-44
suffix tokens each; the session starts empty):

| State | Prefix tokens | State prefill | Three questions |
|---|---|---|---|
| short (fixture 1) | 38 | 3.6 s | 5.7 s |
| long (`speed-bench/promessi_sposi.txt`, first 2000 bytes) | 655 | 9.4 s | 7.0 s |

The question phase includes one snapshot save and two restores. At 31 ms per
token the 107 suffix tokens account for about 3.3 s; the rest (snapshot
copies, per-question first-token cost) was not measured separately. Isolation (fixture 1 alone against the third of three)
and determinism (the same request twice) are bitwise equal.

## 8. Measured (change `820`, 2026-11-12)

`sysone-bench/record.md` has the runs and commands. Template version 1, SSD
streaming, 82 GB expert cache.

| Set | n | Accuracy (95% CI, states) | ECE | Legal mass | p50 / p95 ms per decision |
|---|---|---|---|---|---|
| Italian fixtures | 60 | 0.967 (0.917-1.000) | 0.029 | 0.9999 | 3455 / 5159 |
| typed-decisions test, 100-state subset | 500 | 0.682 (0.638-0.730) | 0.230 | 0.9985 | 3709 / 5176 |

On the full typed-decisions test split others publish Rizzo Flow 0.648, Jev
0.727, Laya fine-tuned 0.766; this model is zero-shot.

- **System One gap** (think minus sysone, 50 typed-decisions items): +12.0
  points (0.720 against 0.600), most of it on `choice`. Generating the answer
  without thinking (`gen`) is no better than reading it (0.679 against 0.675 on
  477 items) and costs about twice the time. Bounded thinking: `860`.
- **Flip rate** under one rotation of choice options: 21.3% on
  typed-decisions, 5% on the fixtures. Position bias is real: `845`.
- **ECE** on held-out typed-decisions: 0.229 raw, 0.042 with one temperature
  per type (noul 8, choice 3.78, score 2.52). The raw probabilities are
  strongly over-confident; use `--sysone-calibration`.
- **Schedule stability**: the top-two option logit gap moves by up to 1.41
  (95th percentile) between layer-major and token-major prefill, and the top
  changes on 4 of 100 decisions. Answers under that gap carry
  `"unstable":true` in `sf` (18% of the typed-decisions answers, 54% right
  against 71%).
- **Abstention**: an explicit option "insufficient: the state does not say"
  detects a state without the answer at AUROC 0.974; abstention needs no
  engine work.

### State cache (change `830`, 2026-11-12)

On 20 typed-decisions states of about 370 tokens (one layer sweep each), one
question per request:

| Request | State path | Wall p50 |
|---|---|---|
| first | miss (prefill) | 12.2 s |
| same state again | hit, 1 ms of state work | 3.2 s |
| state with 59 tokens appended | extend | 5.4 s (12.3 s from scratch) |

A hit is bitwise the first answer; an extension changed the top on 1 of 20
against a from-scratch prefill. Snapshots cost 22.5 MiB at 2K tokens, 58 MiB
at 8K and 200 MiB at 31K; a restore takes 1-20 ms. The cache is keyed on the
state text: a grown state hits only when it extends the old text byte for
byte. A decision between two chat turns no longer costs the chat its prefix
(the next turn prefilled only its 9 new tokens in the live test).

## 9. Conversation as the state (change `835`, 2026-11-12)

With `"sf":{"state":"messages"}` the state is the conversation the slot holds
and each question is asked as the next user turn. After a chat turn with
thinking off the slot's live tokens are a prefix of the rendered conversation,
so a decision prefills only the few new tokens: on 20 typed-decisions
conversations of about 400 tokens the median decision took 2.3 s against
10.2 s for the same conversation sent as a text state (state prefill 32 ms
against 7.7 s). After a thinking turn the live tokens carry the reasoning the
client never sends back, nothing is reused and the conversation is prefilled
again. Details: `sysone-bench/record.md`, "Live state".
