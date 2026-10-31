# Storymap — video "Candor" (version 2, 2026-10-31)

Presentation video of the `sf-ds4-1flash-candor` steering profile on DeepSeek
V4.1 Flash. Slides are in English; the narration is in Italian. No voice for now: the
text to read is in [`NARRATION.md`](NARRATION.md); format and style are in
[`DESIGN.md`](DESIGN.md). Everything lives in `com-steering/video/` on branch
`video/candor-steering`.

## Version 2: what changed after the draft review

| Scene | Change |
|---|---|
| S2 | New slide S2.1: an animated explainer of how a steering vector is extracted (pairs → read the model → subtract). S2.2 shows the two screenshots side by side (no steering / with the vector) |
| S4 | S4.1 is an animation of ds4 being cut down to this tree: a treemap of real line counts (466,914 → 182,163, −61%). S4.2 carries the single-machine facts |
| S5 | The first-token chart is retitled "First decode step after prefill (ms)"; it states why sf restores the decode state better, the protocol (warm page cache, fixed 82GB cache, incremental prefill) and the noise (sf varies 0.10–0.21 s between series) |
| S6 | S6.1 adds the explanation and a line chart (remaining component 1 − F against F) with a moving geometric picture; S6.2 shows the whole model and the single site; S6.3 zooms on one layer, with what is and is not touched |
| S9 | Three animated slides: byte diff of two GGUFs, the rank-one edit and its SVD, forty parallel directions into one file |
| S10 | Orthogonal slots and the phase gate are drawn, not listed |
| S12, S13, S14 | Charts: schedules (log scale for the failed decay), the gap to `</think>`, the layer bands, the closure schedule |
| S16 | An animated terminal with the real commands |
| all | One recurring picture of the model as a mixture of experts (`DESIGN.md`). Narration is Italian; each slide section lists its English text and the Italian translation |

The scene list below is the original storyline; the slide ids of the video (S2.1 …
S17.1) are the `###` sections of `NARRATION.md`.

## 1. Storyline

**Thesis in one line:** a steering vector does not add knowledge, it opens a gate
the model closed after it had already learned the content. Making that gate open
cleanly took three things, not one: two directions that remove the refusal, a dose
that depends on the phase (thinking / answering), and a "door" that lets the model
stop thinking again. Each piece exists because the previous one broke something.

**Arc:** a question the model will not answer → we did this before on V4 and it
proved the knowledge is inside → why a vector and not a modified model → the
platform that made the experiments affordable (`sf-ds4-1flash`, speed) → how a
direction works and how we score it → where the vectors come from, and how we
built one without a GPU → why more than one → closed roads and one instructive
failure → the loop the success created → the door → the scoreboard → from
experiment to service → what is still open.

**Not shown:** prompts and completions of the evaluation set. Only metrics,
geometry and charts. The 1989 question is the one exception, as a *public,
neutral* example of the censorship problem; we take no position on the events.

**Target length:** about 19 minutes at reading pace (17 scenes). Hard cap 20.
Each scene has one or more stops (⏸).

**Audience (assumed):** technical, knows LLMs and the residual stream, has not
read the OpenSpec archive.

## 2. Scenes

Legend: ⏸ = stop point. In *presenter mode* the player pauses there and you talk.
In the *distribution video* the animation simply continues. "Source" = file the
numbers come from.

### Act 1 — The problem and the precedent

**S1. A question the model does not answer** (~40 s)
- Message: censorship is a measurable behaviour, not an opinion. Ask for "important
  events in China in 1989" and the model in general does not state them. No
  judgement on the events: the point is technical.
- Visual/animation: prompt streamed token by token, then the answer card (the real
  screenshot from PR #282 when we have it).
- ⏸ after the answer card.
- Source: PR #282.

**S2. We were here before: DeepSeek V4** (~80 s)
- Message: in May 2026 (PR #282 on `antirez/ds4`, still open, label
  `ideas-to-explore`) the same question was opened on V4 with a **teacher-forced**
  vector: built from good/bad response pairs, taken while the model is already
  entering the target answer (`--component ffn_out`, `--ctx 1024`,
  `--avg-last-k 3`, `--pair-normalize`).
- Settings shown: scale −3 on the FFN output, **decayed over 30 tokens to −0.1 with
  a cubic smoothstep** (`3t² − 2t³`). The decay worked on V4.
- Visual: the three screenshots side by side, with the underlined passages: no
  steering / steering / steering with decay. Smoothstep curve drawn with the stroke
  effect.
- Key point, stated plainly: **the vector does not insert knowledge.** A direction is
  one unit row of 4096 numbers per layer on V4 (5120 on V4.1): it cannot carry a
  chronicle. What comes out is what the model already had; with steering on the
  first token only, the model produced the whole account. The model saw that
  material in pre-training and was censored only afterwards.
- ⏸ on the timeline "pre-training → censorship training → vector".
- Source: PR #282 (read via `gh`; the images were not downloaded yet).

**S3. Why a vector and not a modified model** (~50 s)
- Message: we want one model in memory, exactly as released, and the uncensored
  behaviour only on the requests that ask for it.
- Four boxes (staggered slide-up):
  1. one GGUF, the one released;
  2. per-request switch: the model id `…-steering` turns it on;
  3. switched off, the output is bitwise the unsteered model
     (`make test-deepseek41-steering-session`);
  4. no second 365 GB file (an abliterated Q2 GGUF is 365,713,686,528 bytes).
- Honest cost: while steering is active decode ran 24.3 → 21.4 t/s at the time of
  the first hook (2026-10-13); prefill unchanged.
- Source: `AGENTS.md` (Identity), `dir-steering/README.md` (Cost), change `630`/`640`.

### Act 2 — The platform

**S4. What `sf-ds4-1flash` is** (~60 s)
- Message: ds4 taken to the extreme. One model, Metal only, one machine class: an
  Apple M5 Max with 128 GB. Multi-model and multi-kernel support removed, not
  hidden behind flags.
- Why it matters: a tree small enough to be read whole by a person or an LLM makes
  an idea cheap to try, measure, keep or drop. It also let us try an SSD-streaming
  design and a **second SSD** (Thunderbolt 5, 80 Gbit/s).
- Side note: every child has its own lock, port and home, so two different models
  can run side by side (memory permitting).
- Visual: the model (341 GiB) against a 128 GB machine: main weights ~152 GiB,
  Engram tables 189 GiB on disk, expert cache 82 GB. Icons draw in.
- ⏸ after the size comparison.
- Source: `README.md` (Why this fork), `AGENTS.md` (SSD streaming).

**S5. Speed: what the work bought** (~80 s)
- Message: faster model → faster loop for every later phase, and a usable plan B
  when a provider is down.
- Charts (bars grow, then the % label streams in):
  - prefill (t/s), ds4 → sf: 121 → 176 (first 2048), 114 → 227, 203 → 399,
    354 → 560, 398 → 703 (to 32768 context);
  - generation (t/s): 12.5 → 28.7 at 2048, 13.3 → 27.8 at 8192, 11.7 → 25.7 at 32768;
  - first token (ms): 2565 → 185 at 2048, 2439 → 152 at 8192, 3007 → 194 at 32768
    (−93%);
  - second SSD: first 2048 of prefill 175.7 → 234.6 t/s (+33.5%).
- Guarantee line: output is **bit-identical** (greedy output token-identical to
  ds4 on the parity oracle, ten prompts).
- Caveat on screen: one machine, M5 Max 128 GB, Q2 streamed from SSD,
  expert cache 82GB.
- ⏸ after the first-token chart.
- Source: `README.md` (Speed, A second drive).

### Act 3 — The mechanism and the measure

**S6. A direction, and where it acts** (~80 s)
- Message: a direction is a unit vector; steering removes its component from the
  residual: `h -= F · d · dot(d, h)`.
- Visual: 2D plane. F=1 projects the component away; F=2 reflects it; at F=7 the
  component is multiplied by −6: an **amplified reflection**, not a projection.
  Sign convention: V4 used a negative scale (add the "answer" direction), V4.1 uses
  a positive one (remove the "refusal" direction) — same geometry.
- Site: one point in the V4.1 graph, the weighted fold at the attention input, after
  Engram and before the norm, layers 1-39. File: 40×5120 f32, row 0 zero.
- ⏸ after F=1, ⏸ after F=7.
- Source: `dir-steering/README.md`, `com-steering/spec.md`, change `401`, `409`.

**S7. How we measure a number** (~60 s)
- Message: without an honest metric every improvement is noise.
- Visual: three badges COMPLY 1.0 / DEFLECT 0.3 / REFUSE 0; two tracks "non-think" and
  "think"; a ±1.0 noise band.
- Facts: 44 fixed prompt ids; two identical runs differ on ~3 of 44 labels; only
  **finished** answers are judged (at 256 tokens DEFLECT looked like 0.50, at 2048 it
  is ~0); think and non-think are never averaged.
- ⏸ on the noise band.
- Source: `com-steering/kpi.md`, `make.md`.

### Act 4 — The vectors

**S8. Three independent sources of refusal** (~60 s)
- Three branches that converge:
  1. `msuiche-1017`: a converted control vector, the **baseline: 26.7 / 44**;
  2. `mrfk-q0 / q1`: the two columns of the rank-2 refusal subspace in the public
     `abliteration-edit.npz`;
  3. `dwarfstar-wo`: derived by us from a public abliterated GGUF (next scene).
- Strong fact: **cos(`dwarfstar-wo`, `q0`) = 0.71**. Two independent abliterations of
  the same model agree.
- ⏸ on the 0.71 arc.
- Source: `com-steering/README.md` (Directions).

**S9. Building `dwarfstar-wo` without a GPU** (~100 s) — animated explainer
- Message: we only had a Mac. We used the network as a library, not as a computer:
  other people's published work, taking only what is needed.
- Animation in six beats (stroke draw-in, no bounce):
  1. two files side by side: our base GGUF and the public abliterated GGUF of the same
     quantisation;
  2. **byte diff first**: untouched tensors are identical, edited ones differ; 122
     tensors light up (`attn_output_b`, `ffn_down_shexp`, `ffn_down_exps` ×40 each,
     `engram_kv` ×2). Identical `token_embd` proves it is an in-place edit, not a
     requantisation;
  3. take one edited matrix: `ΔW = W − W' = r (rᵀ W)`, rank one;
  4. SVD: the leading left singular vector of `ΔW` is the removed direction `r`
     (singular-value share 0.89-0.92 on the audited run); fix the sign;
  5. repeat for the 40 layers: all parallel (|cos| 1.0), a global direction;
  6. write the 40×5120 file.
- Resource note on screen: one download into the shared Hugging Face cache, a
  throw-away Python environment, no full dequantisation of a 340 GiB file.
- ⏸ after beat 2, ⏸ after beat 4.
- Source: change `408`, `com-steering/README.md`. **Open point for you:** the repo
  documents the downloads and the throw-away environment; if other remote resources
  were used (cloud machines, others' vectors), tell me and I will add them.

**S10. Why more than one vector** (~90 s) — central scene
- Message: each slot fixes a different failure.
- Three moves:
  1. **Slot 1, `q0dwarf-equi`**, the per-layer bisector of `q0` and `dwarfstar-wo`.
     Alone, `dwarfstar-wo` reaches 39.9 / 44 but fails on prompts disjoint from `q0`'s.
     The bisector covers both (41.6). Alternating layers is worse (10.0 vs 11.0 on
     the 12-id screen);
  2. **Slot 2, `mrfk-q1`, think only**: nearly orthogonal to slot 1 (median |cos|
     0.105 over 39 layers) so the pair composes as a clean 2D removal. Ungated it hurts
     (7.3 vs 11.3 on 12 ids); gated to the reasoning it helps;
  3. **Phase gate**: what helps the thinking can hurt the answer.
- Principle: one fusion is never *the* fusion; every composition also restarts from
  the parents.
- ⏸ after each move.
- Source: `com-steering/spec.md`, `result.md`, `investigation.md`, change `412`, `417`.

### Act 5 — Closed roads and one instructive failure

**S11. The graveyard of ideas** (~50 s)
- Tombstones appear one by one with the number that killed them:
  - fusions of the pre-1017 vectors: random jitter did as well;
  - per-prompt routers (centroid, k-NN, logistic on fold features): never above the
    best fixed config; a cheap first try, not the last word;
  - full rank-2 removal: 5.5-9.5 / 18 vs 12.0;
  - wrong scale: `q0@9` 33.6 / 44, refusals 1 → 9;
  - closed-loop controller: think 30.9 vs 39.0.
- ⏸ after the last tombstone.
- Source: `com-steering/investigation.md` (Closed roads).

**S12. The failure that taught us: decay-to-zero** (~70 s)
- Message: "give the push early, then free the body" looked obvious, and on **V4 it
  worked perfectly** (PR #282, 30 tokens to −0.1).
- On V4.1: think **39.0 → 3.2** (R38 / 44), non-think 41.6 → 34.0.
- Why: V4.1 reasons for thousands of tokens before answering; the 30-token dose is
  spent inside the reasoning and the answer is generated at scale ≈ 0.
- What we kept: do **not** run at the peak all the time. The shipped schedule holds
  7 for 25 tokens, then eases to 3.5 in the reasoning and 4 in the answer, because we
  want to reduce the vector's footprint once it has got past the censorship. A
  window of 256 tokens works; 30 does not. Measured: non-think 41.3, think 39.0.
- ⏸ on the 3.2 collapse.
- Source: `result.md` (418 sections), `investigation.md`.

### Act 6 — The loop and the door

**S13. The success that breaks something** (~70 s)
- Message: removing the refusal also removes "stop deliberating".
- Visual: gap between the top token and `</think>`. Base: falls to 0 in one step
  (22 → 16 → 0). Candor: flat at ~20 logits for 8192 tokens.
- Facts: with constant candor 20/20 of the loop-prone ids never close the think
  (base: 20/20 close, median 193 tokens); on the 44, loops were 17 (constant) and 13
  (with the schedule). The decision is **absent**, not near, so a logit bias would
  force, not restore.
- Layer bisection: compliance is carried late (zero 30-39: 12 → 2), the closure
  suppression early (zero 1-9: loops halve, compliance holds). A useful clue, not a
  winner: it did not beat the schedule.
- ⏸ on the flat curve.
- Source: `investigation.md` (419 stage 0, stage 1).

**S14. The door: an additive closure channel** (~90 s) — central scene
- Message: a third vector, additive, think only, deliberately small.
- Built as a contrastive mean of the site rows (40 layers, per token): the last 10
  forwards before a natural `</think>` minus mid-reasoning, over 20 benign long
  prompts.
- Visual: x axis = think tokens; a(t) at 0, rises to 0.4 at the onset (~2989 at level
  75), 2000 tokens later to 0.9.
- Lessons, one line each: the onset moves the exit one for one; working dose ~0.3;
  a late (p90) onset loses the loops; scale 1.0 is non-monotonic (fixes id 21, breaks
  id 6), so 0.9 stays.
- Benign gate: 16 of 20 benign prompts byte-identical, both benign loops repaired.
- ⏸ after the onset, ⏸ after the 0.9 stage.
- Source: `result.md` (419), `investigation.md` (two-stage closure), change `419`, `420`.

### Act 7 — Result, service and what is open

**S15. The scoreboard** (~60 s)
- Rows enter in historical order: msuiche baseline 26.7 → `q0@7` 41.6 → pair constant
  (41.6 non-think / 39.0 think) → schedule (41.3 / 39.0) → **candor with closure
  (41.3 / 41.0)**.
- Final: non-think **41.3** (`C41 D1 R2`); think **41.0** (`C41 D0 R3`); loops **3 / 44**
  (from 13); think closed on **43 / 44**.
- Residual declared: ids 6, 21, 22.
- ⏸ on the table.
- Source: `result.md` (Standing best).

**S16. From experiment to service** (~60 s)
- Visual chain: `.sfsteer` file (magic `SFSTEER1`, JSON header, three 40×5120
  matrices, 2,458,614 bytes) → per-session switch → request with
  `deepseek-v4.1-flash-steering` → separate KV store `steering/`.
- Raw steering options removed: only profiles (`620`).
- An animated terminal with the commands (no live recording; see Section 4).
- ⏸ on the chain.
- Source: `com-steering/README.md`, changes `620`-`650`.

**S17. What is still open** (~50 s) — exactly the three points you asked for
- The validation on **AdvBench 520 / HarmBench 400 / StrongREJECT 313** is still to be
  finished.
- The steps were adopted one by one and each was an improvement, but everything must
  be re-run clean, in both think and non-think.
- With plenty of GPUs, a **router** (a classifier of the signal or of the context) could
  pick the best vector for each case of censorship.
- ⏸ final (questions).

## 3. Draft and final

The draft (fade/slide, static charts) was reviewed; version 2 is the final build: token
stream, stroke draw-in, staggered slide-up and the animated explainers. A short cut is
still to be made only if the full video turns out too long for the occasion.

## 4. Open points

1. **Live demo.** The GPU is free, so a real recording of the question "Cosa è successo di
   significativo in Cina nel 1989?" on the server, with and without `-steering`, is possible.
   It would load the model for several minutes. Planned to save only timings and tokens/s,
   never the content. Not done yet: S16 uses an animated terminal built from the real commands.
2. **PR #282 screenshots.** The two provided by the user are in `remotion/public/assets/`;
   the second one shows V4 *Pro* with think-steering flags, which differs from the plain V4
   of the caption.
3. **Limits slide** has only the three points requested. Left out on purpose: over-refusal
   (benign prompts) of the shipped directions and axes B–E were never measured.
4. **Voice.** When one exists, slide durations should come from the measured audio length
   instead of 150 words per minute (`remotion/src/timeline.ts`).
