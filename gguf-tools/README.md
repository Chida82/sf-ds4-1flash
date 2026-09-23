# GGUF Tools

This child does not convert or quantize models: the published GGUFs are
downloaded with `./download.sh` and used as they are.

What remains here is measurement:

- [`quality-testing/`](quality-testing/README.md) scores the local model against
  tracked official DeepSeek V4.1 Flash continuations (target-token negative log
  likelihood). Build the scorer from the repository root with
  `make gguf-tools/quality-testing/score_official`; see
  [CONTRIBUTING.md](../CONTRIBUTING.md#quality-checks-for-engine-changes) for a
  before/after comparison.
