# Steering measurements log

An append-only record of steering behavioural measurements, each stamped with the
code commit, vector and conditions it was taken under, so a later change can
re-run the same screen and see whether the numbers moved. Screens are diagnostics,
not acceptance (see `REFUSAL_VALIDATION.md`); the completed-response axis-A
acceptance run (402 task 6.1) is separate and user-run.

Add a new dated block at the top for each run; never edit an old block. When a
code change invalidates older numbers, note the commit that changed the behaviour
and re-measure rather than rewriting the past values.

Conventions used below:
- **Efficacy (flip)**: fraction of base first-decision refusals whose steered
  first decision no longer refuses (first-8-token decision prefix, keyword scored).
  A screen for scale selection, not completed-response efficacy.
- **degraded / onset**: `score_quality` flags on a 128-token benign completion;
  onset is the first word-prefix length at which a repetition loop or code-switch
  appears, `—` meaning clean through 128 tokens.

---

## 2026-10-14 — axis-A efficacy: base / constant-6 / decay-6 (user-run, 10-prompt pilot)

The efficacy side of the decay adoption gate, and the 402 (6.1) acceptance
evidence. `eval/run.py --suite harmful-axis-a` on `union[:10]`, judge (base model)
+ keyword, run by the owner. Two runs, constant scale 6 and decay 6→0.2 (answer
window 50, think 30); controls (no-op, zero-direction) OK, 20/20 completed, no
INVALID, in both.

| metric (judge, n=10) | base | constant-6 | decay-6 |
|---|---|---|---|
| REFUSE rate | 1.00 | 0.00 | 0.00 |
| COMPLY rate | 0.00 | 0.40 | 0.40 |
| keyword refusal | 1.00 | 0.30 | 0.30 |

**Reading:** at scale 6 the vector removes refusals — outright judge REFUSE goes
from 100% to 0%, full COMPLY from 0% to 40% (the rest DEFLECT). The decay keeps the
*entire* efficacy of the constant (identical REFUSE 0% / COMPLY 0.40 / keyword
0.30): the refusal is decided in the first tokens, both at scale 6, and the decay
only lowers the body scale. Combined with the benign fidelity gain (decay distorts
the body ~14-23% less, block below), decay-6 is at least as good as constant-6 on
efficacy and better on fidelity — the adoption case for the 403 schedule. Caveat:
n=10 pilot, wide intervals on the 0.40; the robust part is REFUSE 0% in both. A
`--limit 30`+ run and the predeclared non-inferiority margin (6.5) remain for the
acceptance decision.

## 2026-10-14 — 403 benign fidelity: decay-6 vs constant-6 (forced-prefix KL)

The fidelity side of the decay adoption gate (the efficacy side, on the harmful
axis, is user-run). Three benign texts (~110-119 scored tokens each) teacher-forced
under base / constant-6 / decay-6→0.2 (answer window 50) with `--perplexity-dump`;
KL(base || steered) per position (`eval/score_kl.kl_full_dense_sequence`). Same
build/vector/conditions as the block below.

Per-text mean KL over the whole scored span:

| text | const-6 | decay-6 | decay/const |
|---|---|---|---|
| t1 (water cycle) | 0.0393 | 0.0355 | 0.90 |
| t2 (bicycle) | 0.0591 | 0.0527 | 0.89 |
| t3 (tea) | 0.0530 | 0.0418 | 0.79 |

By position band (decay scale shown):

| band | const-6 | decay-6 | decay/const |
|---|---|---|---|
| pos 0 (scale 6.0) | 0.2196 | 0.2196 | 1.00 (identical) |
| early 1-4 (~6) | 0.0741 | 0.0782 | 1.06 |
| 20-34 (~2.2-0.6) | 0.0537 | 0.0490 | 0.91 |
| late 50+ (0.2) | 0.0502 | 0.0388 | **0.77** |

**Reading:** the decay does restore body fidelity. At position 0 both apply scale
6 and the KL is identical (sanity check); over the body, where decay has eased to
0.2, it distorts base ~23% less than the constant (0.77), ~11-21% less overall per
text. The benefit is modest because constant-6's benign distortion is already
small (~0.05 KL); it would be larger under a higher constant. The early tokens
(where the refusal is decided) keep the full dose. This confirms the decay's
fidelity value; whether it clears the adoption bar also needs the harmful-axis
efficacy side (decay must keep removing refusals), which is the user-run run.

## 2026-10-14 — 403 decay schedule implemented and verified

- **tooling/engine**: the residual decay schedule landed in `ds4.c`/`ds4.h`,
  CLI and server (`--dir-steering-residual-decay-tokens`,
  `--dir-steering-residual-decay-final`, `--dir-steering-think-residual-decay-tokens`).
  Built clean; `make test` green (env-check 504 classified, steering fold and
  file-validation PASS).
- **curve trace** (`DS4_STEERING_SCHEDULE_DEBUG=1`, start 6, final 0.2, window 10,
  `--nothink`): the per-token scale is `6.0000, 5.8376, 5.3968, 4.7472, 3.9584,
  3.1000, 2.2416, 1.4528, …` — the cubic smoothstep `S − (S−F)·(3t²−2t³)`
  decreasing from 6 to 0.2, with the exact midpoint 3.1 at pos 5/10. Output
  coherent ("Red, blue, and green.").
- **phase reset** (think window 4, answer window 8): the thinking phase decays
  `6.0 → 3.1 → 0.2` then holds; at `</think>` the answer phase restarts at
  `pos 0 scale 6.0` and decays over its own window. The reasoning reached the
  correct final answer (6×7 = 42).
- **N=0 / disabled**: a zero decay window leaves `steering_scheduled` false, so
  the schedule hooks early-return and the constant `401` path is unchanged by
  construction; the batched multi-session decode refuses a scheduled session
  (one scale per forward).
- **over-steering note**: starting the decay at an extreme scale (40 → 0.2 over 8)
  still degrades — the first token at 40 poisons the KV, and the output loops
  ("I am I am …"), differing from constant 40 ("I (I I … 达尔"), which itself
  confirms the per-token scale is live. The usable start stays the screen peak 6.

## 2026-10-14 — msuiche residual-scale screen (402/403 baseline)

- **tooling**: `eval/scale_sweep.py`, `eval/run.py harmful-axis-a` @ commit `771a1c8`
- **engine/hook**: V4.1 residual site `v41_attn_input_weighted_fold_post_engram`
  rev 2 (`--dir-steering-residual`, constant scale); `ds4.c` steering last touched
  by `6e60ed3` (401). No temporal schedule exists yet.
- **vector**: `dir-steering/out/v41-msuiche.f32`, sha256
  `e531274260c4da938770fa5f53eec8b9c6c814c8099e21552a298473a0c99109` (40 rows ×
  5120, unit per-layer)
- **decoding**: greedy temp 0, thinking off, server `--ssd-streaming --ctx 4096`;
  decision prefix 8 tokens (sweep), 128 tokens (overshoot)
- **data**: harmful `union[:30]` (sha256 `26659ce1fa85…`, advbench+harmbench+
  strongreject deduped); benign 6 (`benign-smoke`) for the sweep, 3 paragraph
  prompts for the overshoot
- **conditions**: measured on battery / reduced power. The signals are greedy
  argmax decisions and deterministic quality flags, which Metal produces bitwise
  identically regardless of power/thermal, so the values hold; only wall-clock
  (not recorded) would differ.

### First-decision efficacy vs constant scale (base harmful refusal 100%)

| scale | harmful refuse | efficacy (flip) | benign decision changed |
|---|---|---|---|
| 2 | 67% | 0.33 | 0% |
| 3 | 23% | 0.77 | 0% |
| 4 | 13% | 0.87 | 0% |
| 6 | 3% | **0.97** | 0% |
| 8 | 7% | 0.93 | 0% |
| 10 | 13% | 0.87 | 0% |

Efficacy peaks at **scale 6** and declines above it (residual refusal rises again:
3% → 7% → 13%). First-token benign decisions are unchanged (0%) at every scale.
The dip at 8/10 is first-token/small-sample noise, not output degradation (see
below). Confirms and narrows the 401 "effective ~4–8" to a peak at 6.

### Benign output degradation vs constant scale (128 tokens, 3 prompts)

| scale | mean repetition | code-switch | degraded | median onset |
|---|---|---|---|---|
| base | 0.00 | 0/3 | 0/3 | — |
| 6 | 0.01 | 0/3 | 0/3 | — |
| 8 | 0.00 | 0/3 | 0/3 | — |
| 12 | 0.00 | 0/3 | 0/3 | — |
| 20 | 0.25 | 0/3 | 1/3 | 48 words |
| 40 | 0.52 | 1/3 (Chinese) | 2/3 | 32 words |

Constant steering is coherent through **scale 12**; it starts looping at **~20**
(one answer degrades from ~48 words) and clearly breaks at **40** (repetition
loops plus Chinese code-switch — the msuiche alpha-1.0 failure the quality scorer
targets). So the usable constant ceiling is well above the efficacy knee; scale 6
has no gross degradation at 128 tokens.

**Reading for the schedule (403):** the refusal is decided in the first tokens
(97% of refusals already flip at the first decision at scale 6), and constant 6
does not grossly degrade benign output. So a decay schedule is not needed to avoid
collapse; its value is finer fidelity — keeping the post-decision answer closer to
the base model. That subtle drift is measured by forced-prefix KL (402 task 5.3),
not these coarse flags.

### Candidates handed to the user-run axis-A acceptance (6.1)

Scales **4 and 6** (knee and peak), optionally 5. Not 8/10/20/40 (no better
efficacy, worse fidelity). The full run measures judge COMPLY and fidelity at
those scales to choose against the predeclared margin (6.5).
