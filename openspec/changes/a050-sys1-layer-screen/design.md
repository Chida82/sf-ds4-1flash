# Design

Depends on `800` (it calls `sf_sysone` for prompts and the teacher readout)
and on `820`'s item files.

## What the rows are (read before interpreting anything)

`window[L]` holds, for each of the last 128 positions, the 512-value row that
position wrote at layer L. It is computed from layer L's attention input, so
it reflects the residual after layers 0..L−1: **the row at index L is
readable after running L layers.** It is a 512-dimensional normed linear view
of a 5120-dimensional row, stored on an 8-bit float grid. Consequences:

- A probe that **succeeds** on it is strong evidence (the full row holds at
  least as much).
- A probe that **fails** is inconclusive: the missing 4608 dimensions may
  hold the answer. Do not write "layer L does not know the answer".
- 64 of the 512 values carry the position rotation (RoPE). The headline
  figures use values 0..447; the tool also reports all 512. If the two differ
  by more than 5 points at layer 39, say so in the record and ask the owner
  which values are rotated (`ds41_rope_store`, `ds4.c`).

## Snapshot payload layout (private, so assert it)

`ds4_session_save_snapshot(s, &snap, ...)` fills `snap.ptr`, `snap.len`.
All integers are little-endian `uint32`, all rows `float32`:

| Part | Size |
|---|---|
| 13 header words, in order: `0x34565344`, `2`, ctx, `1`, `128`, `128`, ctx+1, **pos**, `40`, `512`, `128`, `129280`, `0x413431` | 52 bytes |
| the checkpoint tokens | pos × 4 |
| the logits | 129280 × 4 |
| 40 windows, layer 0 first; each `raw × 512` values with `raw = min(pos, 128)` | 40 × raw × 2048 |
| (then compressed rows and index keys, not read here) | rest |

The row of token position p in a window is at slot `p % 128` when
pos ≥ 128, else at slot p. The last position is `p = pos − 1`.

The tool MUST check words 0, 1, 3, 4, 5, 8, 9, 10, 11, 12 against the values
above and `snap.len` against at least the size of the parts it reads, and
exit with a message naming the first mismatch. A mismatch means the engine's
format changed: stop and ask; never adjust offsets by trial.

## `sysone-bench/sf_capture.c`

Opens the engine exactly as `tests/test_sysone.c` does for its model-backed
checks, creates one session, calls `sf_sysone_open`. Reads a jobs file and
writes a binary output; one job per line, fields separated by TAB, with `\n`,
`\t` and `\\` escaped inside fields.

Job `D` (decision): `D`, id, type (`noul`|`choice`|`score`), state,
instructions, then name and text for each option (empty text allowed).

```
prefix = sf_sysone_state_prefix(state)
qpart  = prefix + tokens("\n\nQuestion: ") + tokens(instructions)   /* tokenized as two pieces, as 800 does */
full   = prefix + sf_sysone_question_suffix(q)                      /* qpart is a token prefix of full: assert it */
ds4_session_sync(prefix); ds4_session_sync(qpart);  snapshot -> rows_Q (40 x 512 at pos-1)
ds4_session_sync(full);   teacher logits via ds4_session_token_logprob for each option symbol
                          snapshot -> rows_R (40 x 512 at pos-1)
```

Record: `'D'`, `uint32 n_options`, `float32 logit[26]`, `float32 rows_Q[20480]`,
`float32 rows_R[20480]`.

Refuse (skip with a logged line) any job whose prefix is 256 tokens or more:
such a state runs as a sweep and rounds differently from the short ones.

Job `T` (text alone): `T`, id, text.

```
t = ds4_chat_begin; push ds4_token_user; tokens(text)
ds4_session_sync(t); snapshot -> rows (40 x 512 at pos-1)
```

Record: `'T'`, `float32 rows[20480]`.

Records are written in job order; the Python side joins by line number.
Print one progress line per 20 jobs with the elapsed time.

`Makefile`: `sysone-bench/sf_capture` linked like `tests/test_sysone`
(`sf_sysone.o` and `$(CORE_OBJS)`), a target `sysone-capture` that builds it,
and its line in `make help`. Not part of `make test`.

## `sysone-bench/screen_prep.py`

From an item JSONL (`820` format) writes the jobs file: one `D` job per item,
then one `T` job per **unique** pair (instructions, option LINE) with text
`Question: <instructions>\nOption: <LINE>`, where LINE is built as `800`
builds it. Writes a sidecar JSON mapping each item to its `T` job numbers and
to its state id and schema id (the hash of its instructions and option
names).

Items: `fixtures-it.jsonl` (60), the first 240 `typed-decisions` test items
with a state under 250 tokens, and 300 Banking77 test utterances over a fixed
26-intent subset (the 26 most frequent intents of the test split; with 26
options the `800` letter readout is the teacher, no `a040` needed).

Time: about 600 decisions × (3.7 s state + 1.9 s suffix, more for the 26
option lines of Banking77) ≈ 60-80 min, plus a few hundred option texts at
about 0.8 s each. One process, SSD streaming, the `82GB` cache, no `--boost`.
The output is about 600 × 164 KB + options ≈ 0.15 GB in the `--work`
directory; delete it when the record is written.

## `sysone-bench/screen_fit.py`

Pure Python (`array('f')`); run it **after** the capture process has exited.
Splits are by state id (even hash fit, odd hash test) and, separately, by
schema id (half the schemas fit, half test, by hash). Report per question
type; the `choice` rows are the headline.

**Analysis A, in-context probe.** For each layer L in 0..39, on `rows_R[L]`:
answer-symbol centroids exactly as `a055` defines them (mean row per symbol
over fit rows whose teacher top is that symbol, one shared per-dimension
variance, temperature by leave-one-out). Report test agreement with the
teacher top, by state and by schema, and the majority-symbol baseline.
Symbols with fewer than 8 fit rows are excluded and counted.

**Analysis B, similarity readout.** For each layer L:
`q = rows_Q[L]` of the item, `o_k = rows[L]` of option k's `T` job. Subtract
from every `q` the mean of all fit `q`, and from every `o` the mean of all
option rows (removes the common direction). `s_k = cosine(q, o_k)`;
`p = softmax(c · s)` with the single scale `c` fitted by NLL on the fit
states. Report test agreement with the teacher top and accuracy against the
label. `noul` and `score` are reported in a separate table and do not gate
(the literature predicts they fail on similarity; CLM itself maps `noul` to
two sentences).

Unit tests in `tests/test_sysone_bench.py`: the payload parser on a
synthetic payload built by the test (header, tokens, logits, windows with a
known value at the last position, for pos = 5 and pos = 300); centroids on
three synthetic Gaussian classes; cosine readout picks the planted option.

## Verdicts to write in `sysone-bench/record.md`

Analysis A (feeds `a055`):

| Result | Verdict |
|---|---|
| some L ≤ 32 with schema-split agreement ≥ 90% | "go: the answer is linearly readable at L" — `a055` starts, stage 1 at that L |
| best L ≤ 32 below 60% and L = 39 at 90% or more | "the answer forms above layer 32 in this view" — `a055` only on the owner's word |
| L = 39 below 75% | "this 512-value view does not carry the symbol; inconclusive" — `a055` only on the owner's word |

Analysis B (the CLM question):

| Result | Verdict |
|---|---|
| some L ≤ 24 with `choice` agreement ≥ 80% (paired state-level interval of the difference to the teacher excluding −20) | "a similarity readout exists below layer 24" — propose a follow-up: cached option vectors and a zero-suffix readout on the full row |
| every layer below 60% on `choice` and Banking-26 more than 15 points under the teacher | "similarity on these rows does not decide; options must stay in the prompt" — stop the CLM line |
| in between | record the best layer and its figure; no follow-up unless the owner wants a prefilter for more than 255 candidates |

State next to each verdict what a pass would buy, so nobody over-reads it:
per question a similarity readout removes the suffix (1-2 s in `800`'s
layout, 0.25 s in `a015`'s); an early exit at L removes about `(40 − L)/40` of
every token only if `a055`'s timing gate also passes and a later change bounds
the sweep.
