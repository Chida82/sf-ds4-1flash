# Proposal

## Why

Every later System One change (`830` onwards) trades accuracy, calibration and
latency against each other, and `docs/MODEL_KNOWLEDGE.md` lists all three as
unknown for this model: no quality score on the `1017` GGUF, no calibration
figure, no latency distribution for short requests. Without an instrument, a
layout or an early exit would be accepted on impressions. The surveyed systems
also agree that raw probabilities are over-confident until a temperature is
fitted on held-out data (`docs/system-one.md`, section 1).

## What Changes

- `sysone-bench/run.py` (standard library only): sends a JSONL set of
  decisions to `/v1/systemone` and reports accuracy, Brier score, ECE, NLL,
  legal mass, tokens, and latency p50/p95, per question type and overall.
- Three reference modes over the same items, through `/v1/chat/completions`:
  `gen` (thinking off, the answer generated), `think` (reasoning effort high),
  and `teacher` (two `think` runs; an item counts only when both agree). They
  give the price of System One in accuracy against the model's own System 2,
  and labels for unlabelled items.
- `sysone-bench/fit.py`: fits one temperature per question type on a held-out
  half and writes `calibration.json`, bound to the model file and the template
  version.
- Server flag `--sysone-calibration FILE`: applies the temperatures; refuses
  to start when the file's binding does not match.
- A position-bias probe: the same items with the options rotated.
- `sysone-bench/record.md`: one row per run, the baseline first.

## Non-goals

- No new dataset is authored beyond a small Italian fixture set.
- No comparison run against hosted Jev (it needs a key and sends data out).
- No permutation debiasing in the server; the probe only measures the bias.

## Impact

- New directory `sysone-bench/` (scripts, fixtures, record).
- `ds4_server.c`, `ds4_help.c`: the flag. `sf_sysone` is unchanged (it already
  takes a temperature per question).
- `tests/test_sysone_bench.py`: metric unit tests, in `make test`.
