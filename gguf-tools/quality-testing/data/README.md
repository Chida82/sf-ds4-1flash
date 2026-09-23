# Official Quality Fixtures

This directory contains curated hosted-model continuation fixtures that are
safe to commit and use in release QA.

Each fixture directory contains:

- `prompts/case_*.txt`: exact user prompts.
- `continuations/case_*.txt`: deterministic hosted-model continuations.
- `responses/case_*.json`: hosted responses, including logprob slices.
  Some curated sets omit unrelated response IDs and billing fields.
- `manifest.tsv`: paths consumed by `score_official`.

