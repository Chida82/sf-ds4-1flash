# Proposal

## Why

The steering work (`401`, `403`, `404`, `405`) changes what the model refuses.
Without a trusted measurement, "better" is a guess, and the single number
"does it answer harmful prompts?" is maximized by breaking the model. This
change builds the refusal-removal validation framework: an A/B harness, base
vs steered, that says whether an intervention removed refusals, kept the benign
distribution, did not start over-refusing, and kept capability — and that
characterizes **how broad** the removal is (the owner's goal is broad removal,
so breadth is measured, not constrained). It is authored before the
vector-changing work so each later change has a metric. It is model-agnostic
and builds in parallel with `401`; the full A/B loop needs a steered model
(`400`+`401`), but the datasets, scorers and calibration stand alone.

## What Changes

- **Five axes**, every one an A/B of base vs steered, deterministic (greedy,
  temp 0, same chat template and `max_tokens`), raw JSON saved for a manual
  audit of ~10 completions per class:
  - **A. Refusal removal** — `harmful_behaviors[:100]` (distributedcognition's
    exact slice) plus AdvBench, HarmBench, StrongREJECT; scored three ways:
    keyword (overcounts), a 3-way LLM judge (REFUSE/DEFLECT/COMPLY), and the
    StrongREJECT 0-1 rubric.
  - **B. Benign fidelity** — `harmless_alpaca`; KL vs base against a noise
    floor from an identity requant round-trip, plus a code-switching/language
    check (msuiche saw Chinese slip into English answers at alpha 1.0; must be
    ~0).
  - **C. Over-refusal** — XSTest-safe + OR-Bench-hard; false-refusal rate ~=
    base.
  - **D. Capability** — MMLU (ethics/moral_scenarios cluster separate) + GSM8K
    + ARC-c + TruthfulQA; delta ~= 0. Reuses `sf-ds4-1flash-eval` suites where
    they already cover a benchmark.
  - **E. Breadth characterization** — the per-domain map of how far the removal
    reaches. A monitor, not a gate.
- **Multimodal + reasoning axes.** V4.1 is vision: axis A is repeated with the
  harmful prompts rendered as images through the vision tower. Axis A is also
  repeated with thinking on and off.
- **Controls.** A no-op gate (steered at scale 0 reproduces base labels
  exactly, the `make test-deepseek41-decode-switch` idea at the eval level) and
  a null control (a random unit vector of equal norm must not remove refusals).
- **Calibration.** The harness reproduces the published V4.1 numbers so it is
  trusted (see `design.md`). The two published protocols are kept in separate
  report columns, never mixed.
- **Form.** A new `eval/` dir (python) driving the child's CLI, server and
  `sf-ds4-1flash-eval` under `--ssd-streaming`; a `make eval-refusal` target;
  `--judge base|<model>`; datasets fetched to `/tmp`; `out/` raw JSON.

## Capabilities

### New Capabilities
- `steering-validation`: the A/B refusal-removal framework (five axes,
  multimodal and reasoning repeats, no-op and null controls, calibration to
  published numbers, raw-output audit).

### Modified Capabilities
None.

## Impact

- `eval/` (new python): `datasets_*.py`, `compose.py`, `generate.py`,
  `score_keyword.py`, `score_judge.py`, `score_strongreject.py`, `score_kl.py`,
  `score_capability.py`, `run.py` orchestrator, `out/`.
- `Makefile`: `eval-refusal` target (model-backed, follows `gguf/` symlinks).
- `README.md`, `docs/`: how to run it; the two-protocol rule.
- HF dataset IDs drift: loaders try the `walledai/*` mirrors and name the
  missing id on failure.
- Measures `401`, `403`, `404`, `405`; model-agnostic; parallel to `401`.
- Model/eval runs share `/tmp/sf-ds4-1flash.lock`; the harness serializes.
