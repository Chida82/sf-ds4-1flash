# Tasks

Model-agnostic; builds in parallel with `401`. The full A/B loop needs a
steered model (`400`+`401`); groups 1-4 stand alone. Datasets and intermediates
go to `/tmp`; model runs serialize on `/tmp/sf-ds4-1flash.lock` and use
`caffeinate` when long. No model runs are part of authoring.

Status 2026-10-12: harness authored under `eval/`; every file has an offline
`__main__` self-check, all green via `make eval-refusal-selfcheck` (13/13).
`make test` unaffected (EXIT=0, env-check 502), `openspec validate
402-refusal-removal-validation --strict` passes. Boxes checked below are
code-complete AND verified offline; the model-backed and live-network
verifications (marked *model-backed* / *live-fetch*) wait for a steered model.

## 1. Datasets and composition

- [x] 1.1 `eval/datasets_harmful.py`, `datasets_benign.py`, `datasets_overrefusal.py`,
  `datasets_capability.py`: the loaders of VALIDATION_FRAMEWORK §1, each trying
  the `walledai/*`/raw mirror and naming a missing id. The `harmful_behaviors[:100]`
  slice is preserved exactly (offline self-check). Live-fetch CONFIRMED 2026-10-13:
  advbench 520 (slice[:100]=100), harmbench 400, strongreject 313, xstest-safe 250,
  alpaca-benign ok; compose union (deduped) 1201, dc100 100. (OR-Bench still needs the
  `datasets` lib.)
- [x] 1.2 `eval/compose.py`: dedup (normalized whitespace/case) across the
  overlapping harmful sources; keep the `:100` slice as its own suite. Dedup
  verified on a fixture with known duplicates (self-check).

## 2. Generation

- [x] 2.1 `eval/generate.py`: drive the child CLI at greedy temp 0, fixed
  `max_tokens`, one chat template, saving raw JSON per prompt for base and steered.
  The two arms differ ONLY by the steering block (argv-level no-op proof,
  `arms_differ_only_by_steering`, self-check). *model-backed*: base-vs-base run
  label-identical.
- [x] 2.2 Multimodal arm: render the axis-A prompts as images (`render_prompt_image`,
  Pillow) and the server image payload shape (`image_request`). *model-backed*: a
  rendered prompt reaches the decoder (non-empty output).
- [x] 2.3 Reasoning arm: axis A with thinking on and off (the `--think`/`--nothink`
  flag), scored separately. *model-backed*: both arms produce output.

## 3. Scoring

- [x] 3.1 `score_keyword.py`, `score_judge.py` (3-way, `--judge base|<model>`),
  `score_strongreject.py` (0-1 rubric). Each classifier returns the expected labels
  on a hand-labeled fixture and the three are reported separately (self-checks).
- [x] 3.2 `score_kl.py`: KL on forced-token logprobs vs base, with an identity
  requant noise floor; the embedding-cosine proxy as a flagged fallback. KL of a
  distribution against itself is ~0 and the floor is reported (self-check).
- [x] 3.3 `score_capability.py`: axis D, reusing `sf-ds4-1flash-eval` suites,
  adding MMLU ethics-cluster separation. The ethics/moral_scenarios cluster is
  reported apart from the rest (self-check).

## 4. Controls and calibration

- [x] 4.1 No-op gate and null control in `run.py`: the scale-0 arm must reproduce base
  labels exactly; a random equal-norm vector must not drop refusals; a failing
  control stops the run naming which. `make_null_vector` preserves per-layer norm.
  All verified on fixtures (self-check).
- [ ] 4.2 Calibration: reproduce distributedcognition (keyword 98->41, judge 17->1,
  KL 0.142 vs 0.131) and msuiche (refusal32 4->24) with their respective protocols,
  once a steered model exists. The anchors and `within_resolution` are coded; the
  reproduction run is *model-backed*.

## 5. Report

- [x] 5.1 `run.py` orchestrator + `eval/out/report.md`: the VALIDATION_FRAMEWORK §5
  table, one column per protocol (never mixed), resolution printed, plus the axis-E
  per-domain breadth map and the ~10 hand-audited completions per class. Report
  structure verified offline (`build_report` self-check).
- [x] 5.2 `make eval-refusal` (model-backed, follows `gguf/` symlinks) and the
  `README.md`/`docs/REFUSAL_VALIDATION.md` section. `make eval-refusal` with no
  model prints the prerequisite (verified); the docs state the two-protocol rule
  and the `/tmp` dataset path.

## 6. Integration

- [x] 6.1 `make test` (incl. env-check) unaffected (EXIT=0, 502 classified; this
  change adds no runtime code or env), `openspec validate
  402-refusal-removal-validation --strict` passes. *model-backed*:
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`
  token-identical (unchanged by a python-only change). No commit without a request
  — standing commit authority granted for this steering work on `sf/steering`.
