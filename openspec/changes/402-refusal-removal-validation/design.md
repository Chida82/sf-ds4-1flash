# Design

## Context

- A refusal-removal change is only as good as the number that judges it, and
  one number ("answers harmful prompts?") is maximized by over-abliteration
  that breaks the model. The framework is the four-plus-one axes that catch
  that: A down, B/C/D ~= base, E characterizes breadth.
- **Two published V4.1 anchors exist**, and they disagree in scale and scorer:
  - distributedcognition (scale 3.0, n=100, Heretic protocol): keyword 98->41,
    LLM-judge true-refusals 17->1, KL 0.142 vs noise floor 0.131, GSM8K
    14->16/20, MMLU 88.95%->88.95% (ethics -0.14pp), image-harmful 0/10
    refused.
  - msuiche (alpha 0.5, vLLM lane, n=32): refusal32 4->24 comply, cyber32
    5->31, benign32-holdout 32->31 (1 classifier false positive), geopolitical
    29->32, no-op gate 32/32.
  - n=32 resolves ~30 points, n=100 ~10. They are different protocols; mixing
    them in one column is a lie (VALIDATION_FRAMEWORK §7).
- The child already has `sf-ds4-1flash-eval` (`--suite core|hard|all`) for
  capability regression. Axis D reuses it where a benchmark is already covered.
- The owner wants broad removal, so axis E (breadth per domain) is the point,
  not a brake. The harmful-content benchmarks are used to *characterize* reach,
  not to maximize uplift.

## Goals / Non-Goals

**Goals:**
- A trusted, reproducible A/B that ranks interventions `401`/`403`/`404`/`405`.
- Reproduction of both published anchors, so the scorers are calibrated.

**Non-Goals:**
- Deriving or fusing vectors (that is `404`), or any runtime change.
- A single blended score across the two protocols.

## Decisions

### D1. LLM judge, three ways, base model as the default judge
- **Choice.** Keyword (fast, overcounts) + a 3-way judge (REFUSE/DEFLECT/COMPLY)
  + StrongREJECT 0-1, reported separately. Judge defaults to the base model
  classifying its own output (distributedcognition's method), `--judge <model>`
  for an external one.
- **Rejected.** Keyword only — it fires on `illegal`/`disclaimer` inside
  answers that fully deliver, and misses censorship-by-omission.

### D2. KL needs forced-token logprobs
- **Choice.** Axis B KL reads per-token logprobs on the same forced tokens from
  base and steered (the CLI/eval logprob path), against an identity-requant
  noise floor.
- **Rejected / fallback.** The embedding-cosine proxy of changed benign answers
  — kept only as a fallback when logprobs are unavailable, flagged as less
  rigorous.

### D3. Calibration is acceptance, not decoration
- **Choice.** The harness must reproduce distributedcognition's 98->41 /
  17->1 and msuiche's refusal32 4->24 before it is trusted to judge a new
  vector. A deviation means a harness bug, not a model finding.
- **Rejected.** Trusting the scorers blind — judges and keyword detectors
  disagree most on DEFLECT, the class that decides borderline cases.

### D4. Two controls are mandatory
- **No-op gate**: the steered model at scale 0 reproduces base labels exactly;
  if not, the pipeline has a bug. **Null control**: a random unit vector of
  equal norm must not remove refusals; if it does, the harness is measuring
  perturbation, not the refusal direction.
- **Rejected.** Skipping them to save runs — then a green A is unfalsifiable.

### D5. Datasets to /tmp, drift-tolerant loaders
- HF ids move; loaders try the `walledai/*` mirrors and name the missing id.
  Datasets and large intermediates live under `/tmp`, not the repo.

### D6. The first-token screen is the standard pre-gate (added 2026-10-13)
- **Choice.** Every candidate (vector, scale, index, fusion) is screened first
  with the first-token probe: `-n 1 --dump-logprobs`, refusal-opener probability
  mass and top-1 class, base vs steered plus the two D4 controls. One invocation
  costs ~7 s on this machine (the SSD-streaming open is fast), so a 25-prompt x
  2-arm screen is ~6 min and generates no payload. Only candidates that move the
  first token go on to the full-generation axes (A keyword/judge, B KL, C, D).
- **Why.** It settled 401's scale (0.5 is a no-op -> window 4-8), its sign, and
  rejected the +1 index in one evening, cheaply and cleanly. Full generation is
  the expensive confirmation, not the explorer.
- **Rejected.** Full generation on every candidate first: slow, and the
  harmful-generation step is the one the agent cannot run.

## Risks / Trade-offs

- **[Judge is the base model, which was steered in the B arm]** -> judge with a
  frozen base checkpoint, never the steered one; the judge arm is fixed across
  A and B.
- **[n=32 vs n=100 scales invite mixing]** -> the report keeps a column per
  protocol and prints the resolution (~30 vs ~10 points) next to each.
- **[Model runs are slow and share the lock]** -> the harness serializes, uses
  short `max_tokens`, `caffeinate` for long runs, and the large unions only for
  publishable numbers (the :100 slice for the DC comparison).
- **[Raw automation drifts from truth]** -> ~10 completions per class per axis
  are read by hand; the judge/keyword gap is reported, not hidden.
