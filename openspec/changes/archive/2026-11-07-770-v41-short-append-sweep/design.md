# Design

## Context

`ds41_prefill_count` decides how many rows of a prompt the next call
prefills: a count above one is a layer sweep, one is a token-major step. The
first call of a session uses a 256-row minimum. Once the session holds context
(`g->pos > 0`), upstream raises the minimum to 1024 when the expert cache has
at least half of all routed experts (40 x 384 / 2 = 7680 slots), on the
grounds that warm short appends beat a full disk sweep and that a
token-major tail warms the decode cache. At `80GB` (7810 slots) and `82GB`
(8026) that rule applies to every chat turn and to every prompt tail under
1024 rows.

## Measurement

Probe (2026-11-07, `80GB`, 32K allocated, one bench session per run: a
2048- or 8192-token context, then appends of 64, 128, 256, 384, 512, 768 and
1000 tokens with 16 decoded tokens after each; token-major is the default
1024, sweep is `DS4_METAL_V41_WARM_APPEND_MIN=32`; ABBA, two runs per mode,
each from 47 C; time to first token = prefill + first decoded token, median):

| append | 2K token-major | 2K sweep | 8K token-major | 8K sweep |
|---|---|---|---|---|
| 64 | 2.0 s | 6.2 s | 2.0 s | 6.3 s |
| 128 | 4.2 s | 6.3 s | 4.2 s | 6.2 s |
| 256 | 8.1 s | 6.5 s | 7.9 s | 6.5 s |
| 384 | 12.7 s | 6.9 s | 12.6 s | 6.8 s |
| 512 | 15.9 s | 6.6 s | 16.2 s | 6.8 s |
| 768 | 24.4 s | 6.8 s | 24.5 s | 6.8 s |
| 1000 | 32.6 s | 7.0 s | 32.6 s | 6.9 s |

- A sweep of 64-1000 rows costs 6.0-6.7 s of prefill, nearly independent of
  its length, plus a first token of about 0.2 s (the decode cache is colder
  after a sweep: 0.03 s after token-major rows).
- Token-major costs 31-32 ms per row, at 2K and at 8K alike.
- The two runs of each cell differ by at most 0.5 s token-major and 0.2 s
  sweep, so the break-even, about 200 rows, is resolved.
- Steady decode after the append (15 tokens) was not slower after a sweep
  (29-33 t/s in both modes).

## Decision

Under single-box SSD streaming the warm minimum is 256 rows, the same as the
cold minimum: every append of 256 rows or more is a sweep. 256 rather than
the 200-row break-even because 256 is the minimum the first call already uses,
it leaves the 200-255 band (within 1.3 s either way) to the path that keeps
the decode cache warm, and it needs no new constant. Resident and TP sessions
keep upstream's rule, which this probe did not measure.

`DS4_METAL_V41_WARM_APPEND_MIN=<rows>` sets the minimum where upstream's warm
rule applies (streaming, cache at least half full, one box); `1024` restores
upstream's schedule, bitwise.

## Correctness

- Both paths already run in this build for the same rows: the first call of
  every session sweeps from 256 rows, and a cache under 7680 slots sweeps
  every append from 256 rows. No kernel changes.
- `DS4_METAL_V41_WARM_APPEND_MIN=1024` against `main`: bench frontier and
  post-decode logits at 2048, +448 and +896 bitwise equal (6 of 6 files).
- Default against `main`: the same argmax after both appends, logits within
  1.37; the 16 greedy tokens after each append diverge, as any change between
  batched and token-major arithmetic does.
- `tests/test_deepseek41_prefill.c` checks the dispatch table with and
  without the variable, and the short-sweep merge invariant.

## Risks

- The tokens of a chat or of a prompt tail of 256-1023 rows no longer match
  upstream's. The parity oracle's prompts do not reach the rule.
- The first token after an append is about 0.17 s slower; the append itself
  is 1.6-26 s faster from 256 rows.
- `DS4_METAL_DISABLE_V41_MEDIUM_SWEEP` no longer restores a token-major tail
  for 2049-8191-row remainders whose tail has 256-1023 rows: the short sweep
  now merges it (the dispatch test records 5000 -> 5000; `1024` gives 4096).
