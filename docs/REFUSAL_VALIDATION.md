# Refusal-removal validation

The `eval/` harness (OpenSpec 402) measures whether a steering intervention
(`401`, `403`, `404`, `405`) removed refusals **without** breaking the model. A
single number — "does it answer harmful prompts?" — is maximized by
over-abliteration that wrecks the model, so the harness scores five axes as an
A/B of a base run against a steered run, with identical decoding (greedy, temp 0,
one chat template, fixed `max_tokens`). Any difference in decoding between the two
arms is a harness fault, not a model finding.

## The five axes

- **A. Refusal removal** — AdvBench `harmful_behaviors[:100]` (distributedcognition's
  exact slice), plus the deduped union of AdvBench/HarmBench/StrongREJECT. Scored
  three ways, reported separately: keyword (fast, overcounts), a 3-way LLM judge
  (REFUSE/DEFLECT/COMPLY), and the StrongREJECT 0–1 rubric. Repeated with the
  prompts rendered as **images** through the vision tower, and with **thinking on
  and off**.
- **B. Benign fidelity** — Alpaca harmless instructions: KL of the steered
  next-token distribution from base on forced tokens, shown next to an
  identity-requant **noise floor** (a KL below the floor is model equivalence,
  not a shift), plus a code-switching / language check (msuiche saw Chinese slip
  into English answers at alpha 1.0; must be ~0).
- **C. Over-refusal** — XSTest-safe + OR-Bench-hard: the false-refusal rate must
  stay ~= base.
- **D. Capability** — reuses `sf-ds4-1flash-eval` (`--suite core|hard|all`) and
  adds the MMLU ethics-cluster separation, so a values shift can't hide inside an
  overall-flat score. Delta ~= 0.
- **E. Breadth** — the per-domain map of how far the removal reaches. The owner's
  goal is **broad** removal, so E is a **monitor, not a gate**.

## Two controls (mandatory)

- **No-op gate**: the steered model at scale 0 must reproduce base labels exactly.
  If not, the pipeline has a bug.
- **Null control**: a random unit vector of equal per-layer norm must not remove
  refusals. If it does, the harness is measuring perturbation, not the refusal
  direction.

A failing control stops the run and names which failed.

## Two protocols, never mixed

Two published V4.1 anchors calibrate the scorers, and they disagree in scale and
scorer. They are kept in **separate report columns** with each column's resolution
printed; blending them into one score is a lie.

| Anchor | Protocol | Resolution | Base → steered |
|---|---|---|---|
| distributedcognition | Heretic, n=100, scale 3.0 | ~10 points | keyword 98→41, judge 17→1, KL 0.142 vs floor 0.131, GSM8K 14→16 |
| msuiche | vLLM, n=32, alpha 0.5 (knee) | ~30 points | refusal32 comply 4→24, no-op gate 32/32 |

The harness must reproduce these before it is trusted to judge a new vector; a
deviation is a harness bug, not a model finding.

## Running it

Datasets and large intermediates go to `/tmp` (override with `SF_EVAL_CACHE`), not
the repo. Raw completion JSON lands in `eval/out/` (gitignored).

```sh
# model-less logic checks of the harness itself (seconds, no model):
make eval-refusal-selfcheck

# full A/B loop (model-backed, long SSD-streaming runs):
make eval-refusal EVALFLAGS="--steer dir-steering/out/v41-fused.f32 --residual 4 --protocol both"
```

**Intervention identity.** The steered arm runs at the `401` site,
`v41_attn_input_weighted_fold_post_engram` revision 2, which the CLI prints at
startup (`ds4: V4.1 residual steering: <file> at <site> rev <N>, scale <F>`). A
run records that line, the vector's sha256 from the converter sidecar and the
scale; results measured under another revision are not comparable. The
first-token screen of 2026-10-13 (scales 0.5 to 16) predates revision 2 and is
screening history, not acceptance.

With no model present, `make eval-refusal` prints the prerequisite and stops.
`--judge base` (default) uses the base model to classify its own output
(distributedcognition's method); `--judge <model>` swaps in an external judge.

About ~10 completions per class per axis are meant to be read by hand: automation
drifts from truth, and the judge/keyword gap is reported, never hidden.
