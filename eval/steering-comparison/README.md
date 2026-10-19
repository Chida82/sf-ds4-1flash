# Steering comparison

A way to put several steering vectors side by side on one axis and read one
matrix. A *vector* is a file plus a scale. An *axis* is a prompt suite plus a
*scorer*: the scorer decides what counts as the vector working on that axis
(longer answers, a format kept, a language held, a tone, a judged outcome). The
tool does not define the axis; it measures whichever one the scorer encodes.

Tool: `eval/compare_steering.py`. **How to test, the scorers, and the current
values are in `STEERING.md`.**

## Scoring

Per prompt, per vector:

| Verdict | Value | Mark |
|---|---:|:--:|
| Work | 1.0 | `P` |
| Partial | 0.3 | `p` |
| NotWork | 0.0 | `B` |
| not measured | — | `-` |

A vector's score is the sum over the prompts; its mean and a bootstrap 95% CI
go in `totals.json`, with the raw P/p/B counts and the mean at every Partial
weight in 0.2, 0.3, 0.4, 0.5 (`--partial-weight` picks the one in use). Vectors are compared only on ids they all share: a ragged
matrix is not a comparison.

## Layout

```
eval/steering-comparison/
  README.md            this file: what the folder is
  STEERING.md          how to test, scorers, current values, next steps
  TODO.md              progress, resume point, where every piece of data is
  stages.sh            two-stage axis-a screening queue (resumable)
  axis-a/stages/       one marker per finished stage: run id + score
  <axis>/base.jsonl    unsteered completions
  <axis>/<name>.jsonl  one steered vector's completions
  <axis>/matrix.md     the P/p/B matrix
  <axis>/totals.json   per-vector score, mean, 95% CI, coverage flag
```

The `<axis>/` run outputs are gitignored like other `eval/out` data; commit a
`matrix.md` only when it is meant to be kept.
