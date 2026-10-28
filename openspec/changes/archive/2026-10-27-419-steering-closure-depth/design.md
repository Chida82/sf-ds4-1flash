# Design

## Context

See proposal.md, "Why". Facts the approach rests on:

- The steering site is the attention input `g->x` of each V4.1 layer (the weighted
  HC sum after Engram, before the norm); the fold `h -= s·d·<d,h>` only subtracts.
- Think/answer phase and the in-phase token index already exist on the session
  (`steering_in_think`, `steering_phase_tok`, 418) but are maintained only while a
  slot is gated or scheduled; a base run tracks nothing.
- The CLI decodes one token per forward; the logits are on the CPU after every
  forward (`s->logits`), so a probe is a `fprintf`, not a kernel.
- The harness (`eval/run.py`) runs one CLI process per prompt and arm, sequentially,
  inheriting the environment; a steered arm differs only by `--steering-profile`.
- The shipped candor is 418-C; the constant candor the stage-0 comparison needs is
  no longer a file (pruned at `6f87c4f`) and is rebuilt with `make_profile.py`.

## Goals / Non-Goals

**Goals:**
- Stage 0 gives, from one run per arm, the closure gap over position for base and
  constant candor, and therefore an offline prediction of every stage-2 schedule.
- Every stage keeps unsteered output bitwise identical and keeps a profile without
  the new fields bitwise identical.

**Non-Goals:**
- No change to the shipped profile inside this change (re-recording is a later,
  evidence-backed step, see proposal "Not in scope").
- No per-layer graded scale in stage 1 (0/1 mask only).

## Decisions

1. **Probe writes a trace file named by the env, not stderr.** The harness keeps a
   process's stderr only on failure (`stderr_tail`), so a stderr probe would be lost
   on every successful prompt. An append-mode file named by
   `DS4_V41_CLOSURE_GAP_TRACE` survives the harness unchanged; `begin` lines carry
   the prompt length, the steered flag and the opening phase, which is enough to
   align the trace with the manifest offline (the harness runs base for all prompts,
   then steered, in manifest order). Alternative rejected: a new harness option that
   routes stderr to a file (touches `eval/` for a one-off).
2. **Phase tracking is shared, not duplicated.** When the probe is on,
   `ds41_steering_on_prompt/on_decode` run their phase bookkeeping even for an
   unsteered session, and apply the gates only when a slot is live. The base arm
   then has the same `steering_phase_tok` as the steered one, so positions compare
   directly. Alternative rejected: a second pair of phase fields for the probe.
3. **Stage 0 runs without `--base-from`.** The cached base cells carry no trace, so
   the base arm is generated again on the 20 ids (base think answers are short:
   minutes, not hours). The run keeps the proposal's harness flags otherwise.
4. **Stage 1 is files only.** Masks come from `dir-steering/tools/mask_layers.py
   --zero-layers`, profiles from `make_profile.py` identical to the constant candor
   except for the equi matrix. No engine change, no new field.
5. **Stage 2 bias is applied at the sampling entry points, on the CPU logits**, as a
   per-session value computed by the same per-token path as the 418 schedule, so it
   composes with the fold slots and costs nothing on the GPU. Fields live in the
   `.sfsteer` header; absent fields leave the path untouched. Budget forcing injects
   `think_end_id` at `B(N)` think tokens from the same site.
6. **Stage 3 adds a third, additive channel**, a new kernel on the BF16 `g->x`, with
   its own direction tensor and an `a=0` bitwise check written before tuning. The
   contrastive direction needs the activation capture at the ds41 site, which is the
   stage's first task because the generic dump hook never fires on this graph.

7. **Closure onset floor, think-level coupled (owner, 2026-10-25).** Any closure
   lever (stage-2 bias or budget, stage-3 vector) pushes *little* and never before a
   floor that grows with the think-level N: no closure pressure before 256 think
   tokens at N ≤ 10 and before 2560 at N = 100, linear in between
   (`T0(N) = 256 + 2304·(N−10)/90` for N > 10, so 1920 at the harness's N = 75).
   The stage-0 base traces support the "little" part: the natural `</think>` is a
   cliff (median gap 16 logits one forward before the exit, 0 at it), so a small
   push cannot fire early; its risk is being inert, not harmful.
8. **Screen set.** Loop fixes are screened on the 20 constant-candor loop ids plus
   the 13 ids that still loop under the shipped 418-C profile (run `20261025-154338`,
   completion length ≥ 28000 chars as the proxy; 9 of them overlap): 24 ids. The
   418-C loopers are the residual problem the change exists for.

9. **The stage-3 direction is "satisfied, done", captured on benign reasoning
   (owner, 2026-10-25).** The additive vector offers a door, not an order: it moves
   the state toward "I have reasoned enough and am content to close", and the model
   decides whether to walk through. So the contrastive capture must not use the
   base refusals of the harmful set (they close at 120-430 tokens because the model
   has decided to refuse: the wrong satisfaction). Capture on benign prompts that
   need long reasoning and close on their own (math, code, planning): positions in
   the last ~10 forwards before a natural `</think>` minus positions mid-reasoning
   of the same prompts (and minus candor mid-loop positions as a second contrast).
   The unembedding (A) and lexical (B) vectors are the bare door and stay as
   secondary candidates.

## Risks / Trade-offs

- [The 20-id stage-0 run takes ~3 h: constant candor loops to the 8192 cap on
  ~17/20 ids] → launch detached under `caffeinate -i`, monitor with
  `SF_EVAL_PROGRESS_FILE`; one engine open per prompt is the harness's normal cost.
- [A gap trace per token on a looping prompt is ~8k lines] → 20 ids × 2 arms is a
  few MB; acceptable, no sampling.
- [Phase bookkeeping now runs on base sessions when the probe is on] → gated behind
  the env; the gates themselves are applied only when a slot is live, so an
  unsteered run with the probe on is bitwise the run without it.
- [Stage 1's mask also acts in the answer phase] → every winning mask gets the 44-id
  non-think guard before it is considered.
- [The closure channel and the site capture route the HC block input through
  the unfused path (the fused kernel returns before the site)] → the fusion
  switches already claim bitwise identity for that path; the `a=0` check and a
  capture-on vs capture-off token comparison verify it before any tuning.
- [Stage 2 replaces the closing decision instead of restoring it] → recorded as the
  floor; stage 3 is still tried when loops stay above t1's 11/44.

## Owner's sketch for stage 3 (reproduced in full)

Design sketch (owner, 2026-10-25) for breaking the candor think loop with a derived
closure vector, not a compliance schedule. Call these the **antiloop** vectors.

**Mechanism.** The loop is a suppressed `</think>` exit. The antiloop vector is
ADDED to the residual to slightly raise P(`</think>`). It must only *nudge* the
closure up, never force it: too strong interrupts a legitimate thought. The whole
lever is the scale being small.

**Schedule (progressive, rising, think-level-coupled):**
- 0 for the first ~500 think tokens (let the model reason), then rises.
- Onset/slope inverse to the think-level (think-level = the soft "Reasoning
  Effort: N" prompt text, N=75 default; the model closes on its own, nothing forces
  it). think=100 → rises to low values only after many tokens (long reasoning
  allowed). Low think → rises more, after few tokens (close sooner). The vector
  enforces what the effort text only hints.
- The rising schedule is the opposite of the 418 decay; reuse the smoothstep
  infrastructure as a ramp-up keyed off `steering_phase_tok` and the think-level.

**Vectors available (derived and compared, ~orthogonal to each other and to
compliance):** A = `com-steering/vectors/v41-think-unembed.f32` (unembedding row of
`</think>`, id 128822); B = `com-steering/vectors/v41-closure-lexical.f32`
(closure-minus-continuation lexical). Experiment: one, both, different scales.

**Blockers (supervised engine work):** the fold only subtracts; an additive push
needs a new Metal operator. Testing via activation capture is blocked (the dump does
not fire in the ds41 graph). t1-holdhalf is the schedule-only fallback that already
works.

## Open Questions

- Which think-levels to sample for the inverse coupling in stages 2-3 (75 is the
  harness default; 25 and 100 are the natural extremes). Decidable after stage 0's
  gap curves exist; it changes parameters, not the approach.

## Spec delta scope

Stages 0 and 1 add one probe and vector files; the delta spec holds the probe
requirement only. The stage 2 (closure bias, budget forcing) and stage 3 (additive
third channel) requirements are added to the delta when the first of those stages is
implemented, as the proposal states.
