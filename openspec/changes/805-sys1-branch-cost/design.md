# Design

Depends on `800` and `810`. Read `docs/system-one.md` section 7 first.

## Interface

```c
typedef struct {
    double prefill_ms;  /* ds4_session_sync of the state prefix */
    double save_ms;     /* ds4_session_save_snapshot; 0 with one question */
} sf_sysone_timing;
```

`sf_sysone_decide` gains a last argument `sf_sysone_timing *timing` (may be
NULL). Every caller passes NULL except the server and the test. Inside the
question loop:

- `restore_ms`: around `ds4_session_load_snapshot` plus the two asserts; 0 for
  the first evaluated question.
- `eval_ms`: around `ds4_session_sync(full)` only.
- `ms` (from `810`) stays the whole question.

Use `CLOCK_MONOTONIC`, already used by `sf_sysone.c`.

## Server

`sf` object: `"save_ms"` at the top beside `prefill_ms`, which now comes from
`timing.prefill_ms` instead of `total − Σ ms`; per question `"restore_ms"` and
`"eval_ms"`. Golden-string test in `ds4_server.c` updated.

## `--timing` mode

Engine opened as in `test-sysone` (32 GiB cache, ctx 4096). For each state in
{fixture 1 (38 tokens), the 655-token `promessi_sposi.txt` prefix} and each
question count in {1, 3, 6} (questions: fixtures 1, 2, 3 repeated), three
repetitions. Before each repetition sync a different 10-token state, so every
run starts from a non-matching session. Print one row per run:

```
timing state=38 q=3 rep=1 prefill=3590 save=410 restore=[0,380,377] eval=[1210,980,1450] readout_total=5676
```

Then a summary row per (state, q): medians.

Also print, for the 38-token state, `prefill_ms / prefix_tokens`, and run the
same state a second time without the intervening reset (session matching):
the difference between a cold and a warm expert cache is then visible as the
difference between rep 1 and a fresh-process first rep. Run the whole mode
twice in two processes and keep both outputs.

## Decision rules (write the outcome in the record)

1. `save + Σ restore > 0.3 × question phase` (medians, 3 questions): write a
   follow-up proposal `806-sys1-branch-restore` naming the slow part. Read
   `ds4_session_load_snapshot` in `ds4.c` to name what it copies (host bytes,
   GPU buffers, compressor state) before writing it.
2. `eval_ms / suffix_tokens > 62 ms` (twice the decode rate) on warm runs:
   record per-token cost against position in the suffix; if the first few
   tokens carry most of it, say so.
3. Otherwise record "branch overhead within budget" and close.

## Risks

None to output: the change only adds clocks. The test checks that answers
with `timing` non-NULL are bitwise equal to answers with NULL.
