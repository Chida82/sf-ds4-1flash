# Tasks

Model-agnostic; builds in parallel with `401`. The full A/B loop needs a
steered model (`400`+`401`); groups 1-4 stand alone. Datasets and intermediates
go to `/tmp`; model runs serialize on `/tmp/sf-ds4-1flash.lock` and use
`caffeinate` when long. No model runs are part of authoring.

## 1. Datasets and composition

- [ ] 1.1 `eval/datasets_harmful.py`, `datasets_benign.py`, `datasets_overrefusal.py`,
  `datasets_capability.py`: the loaders of VALIDATION_FRAMEWORK §1, each trying
  the `walledai/*` mirror and naming a missing id. Verify each returns a non-empty
  list offline-cached, and the `harmful_behaviors[:100]` slice is preserved exactly.
- [ ] 1.2 `eval/compose.py`: dedup (normalized whitespace/case) across the
  overlapping harmful sources; keep the `:100` slice as its own suite. Verify dedup
  on a fixture with known duplicates returns the expected unique count (`__main__`
  assert self-check).

## 2. Generation

- [ ] 2.1 `eval/generate.py`: drive the child CLI/server at greedy temp 0, fixed
  `max_tokens`, one chat template, saving raw JSON per prompt for base and steered.
  Verify a base-vs-base run is label-identical (the no-op path of the harness).
- [ ] 2.2 Multimodal arm: render the axis-A prompts as images and send them through
  the vision tower. Verify a rendered prompt reaches the decoder (non-empty output).
- [ ] 2.3 Reasoning arm: repeat axis A with thinking on and off. Verify both arms
  produce output and are scored separately.

## 3. Scoring

- [ ] 3.1 `score_keyword.py`, `score_judge.py` (3-way, `--judge base|<model>`),
  `score_strongreject.py` (0-1 rubric). Verify on a tiny hand-labeled fixture that
  each classifier returns the expected labels and the three are reported separately.
- [ ] 3.2 `score_kl.py`: KL on forced-token logprobs vs base, with an identity
  requant noise floor; the embedding-cosine proxy as a flagged fallback. Verify KL of
  a distribution against itself is ~0 and the floor is reported.
- [ ] 3.3 `score_capability.py`: axis D, reusing `sf-ds4-1flash-eval` suites where
  they cover a benchmark, adding only MMLU ethics-cluster separation and any missing
  set. Verify the ethics/moral_scenarios cluster is reported apart from the rest.

## 4. Controls and calibration

- [ ] 4.1 No-op gate and null control in `run.py`: the scale-0 arm must reproduce base
  labels exactly; a random equal-norm vector must not drop refusals. Verify both
  controls on a fixture and that a failing control stops the run naming which.
- [ ] 4.2 Calibration: reproduce distributedcognition (keyword 98->41, judge 17->1,
  KL 0.142 vs 0.131) and msuiche (refusal32 4->24) with their respective protocols,
  once a steered model exists. Verify each anchor is within its resolution; a miss is
  flagged as a harness bug, not a model finding.

## 5. Report

- [ ] 5.1 `run.py` orchestrator + `eval/out/report.md`: the VALIDATION_FRAMEWORK §5
  table, one column per protocol (never mixed), with resolution printed, plus the axis-E
  per-domain breadth map. Verify the report names base and steered, keeps the two
  protocols in separate columns, and lists the ~10 hand-audited completions per class.
- [ ] 5.2 `make eval-refusal` (model-backed, follows `gguf/` symlinks) and the
  `README.md`/`docs/` section. Verify `make eval-refusal` with no model prints the
  prerequisite, and the docs state the two-protocol rule and the `/tmp` dataset path.

## 6. Integration

- [ ] 6.1 `make test` (incl. env-check) unaffected (this change adds no runtime code
  or env),
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` still
  token-identical, `openspec validate 402-refusal-removal-validation --strict`. No
  commit or push without a request.
