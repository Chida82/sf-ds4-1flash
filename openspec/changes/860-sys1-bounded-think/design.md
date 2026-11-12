# Design

Depends on `810`, `820`; stage 2 depends on `840`.

## Token ids without engine internals

```c
ds4_tokens t = {0};
ds4_chat_append_assistant_prefix(e, &t, DS4_THINK_NONE);  /* t.v[1] is </think> */
ds4_chat_append_assistant_prefix(e, &t, mode);            /* t.v[3] is <think>  */
```

`mode` comes from `ds4_think_mode_parse_level("25", &mode)` (the level as
text). Keep both ids in `sf_sysone`.

## Prompt (stage 1, `state_first`)

The reasoning-effort line lives in the system turn, so a thinking request has
its **own state prefix** (and its own `830` cache key, which follows from the
key being the tokens):

1. `ds4_chat_begin`
2. `ds4_chat_append_think_prefix(e, &t, mode)` (the effort line)
3. `ds4_chat_append_message(e, &t, "system", SYS)` (it adds no second system
   marker when the prefix already carries one)
4. user marker, `"State:\n"`, state

Suffix: as `800` up to the instruction line, then
`ds4_chat_append_assistant_prefix(e, &t, mode)` (assistant marker and
`<think>`). **No answer prefill yet.**

Then, per question:

```
sync(prefix + suffix)
n = 0; closed = false
while n < N:
    tok = ds4_session_argmax(s)
    if ds4_token_output_marker(e, tok) == DS4_OUTPUT_MARKER_THINK_CLOSE: closed = true; eval(tok); break
    if ds4_token_is_stop(e, tok): break
    ds4_session_eval(s, tok); n++
if !closed: ds4_session_eval(s, think_close_id)        /* forced */
full = copy of ds4_session_tokens(s) + tokens of the answer prefill
ds4_session_sync(s, full)
readout as in 800
```

The response's `sf` object reports per question `think_tokens` (generated)
and `think_closed` (`"natural"` or `"forced"`). `usage.output_tokens` is the
sum of generated thinking tokens.

With `N = 0` the request takes the `800` path unchanged (thinking off, no
effort line): bitwise the same answers as before this change.

Context check: prefix + suffix + N + prefill must be under the context, or
400 `max_tokens_exceeded`, before any evaluation.

## Step 0: one trajectory run answers every N (before building the option)

Running the bench once per N wastes the machine: one thinking pass contains
every budget. `tests/test_sysone --think-trajectory` (about 60 lines on the
public API, in the test file) does, per item:

```
sync(thinking prefix + suffix + assistant marker with <think>)
n = 0
loop:
    if n % 32 == 0:                      /* a probe: what would a forced close answer here? */
        save snapshot
        eval(think_close_id); sync(+ answer prefill); read option logits and legal mass -> row (n)
        load snapshot
    tok = ds4_session_argmax(s)
    if tok closes the reasoning or is a stop token: break
    eval(tok); n++
    if n == 1024: break
final: eval(think_close_id) unless the model closed; sync(+ answer prefill); read -> row ("natural" or 1024)
```

A probe costs a snapshot save and load plus about 6 tokens (0.2 s), every 32
reasoning tokens: about 20% on top of the thinking itself. The probes do not
change the reasoning: each one is undone by the snapshot.

Run it on the 12 fixtures of `800`, then on 200 items from `820` (prefer
items where the N = 0 readout and the `think` answer disagree: they are the
ones thinking can change). One run gives, for every N in 0, 32, 64, …:

- accuracy and ECE if the request had stopped at N (the whole curve);
- mean legal mass of a **forced** close at N, the unknown this change rests
  on;
- per item, the first N from which the top option no longer changes
  (a stabilisation histogram).

Go on to the option only if at N = 64 the mean legal mass is at least 0.5 and
some N ≤ 256 has an accuracy interval (resampled by state) wholly above
N = 0's accuracy. If legal mass fails, try once with the forced text
`"\nSo the answer is clear."` evaluated before the close. If that fails too,
stop: record the curves under "Considered and not proposed" in
`docs/system-one.md` and archive the change as rejected.

"Stop when the answer has converged" (probe during the reasoning and exit
after two equal tops) is published work (Dynasor-CoT, DEER) and was judged
not worth a separate change here: where decisions converge at N = 0 the
plain readout already answers, and where thinking matters the confirmation
lag eats the saving. The histogram above will show whether that judgment
holds for this model; if more than half the items stabilise before a quarter
of their natural length, say so in the record and ask the owner.

## Bench confirmation

After the option exists, one confirming run through HTTP at the chosen N and
at N = 0 on the same 200 items, effort 25 and 75. One row each in
`sysone-bench/record.md`. Kept when the chosen N's accuracy interval is
wholly above N = 0's. Otherwise remove the option and keep the record.

## Stage 2: think once, answer many (`schema_first` only)

Prefix: effort line, `SYS2`, user marker, the schema, the state, then
`"\n\nThink about the state with respect to every question. Do not answer yet."`,
assistant marker with `<think>`; generate up to N tokens with the loop above;
force the close if needed; evaluate the tokens of `" Ready."`. **Snapshot
here.** Per question: user marker, `"Answer Q" i "."`, assistant prefix with
thinking closed, `"Q" i ": ["`, readout, restore.

Cost: one reasoning pass per request instead of one per question, and
0.3 s per question after it. Bench it at the best N of stage 1 against
per-question thinking on grouped items; keep it under the same rule
(accuracy interval not wholly below per-question thinking, latency lower).

## Tests

Model-less: the loop's control flow on a fake session interface is not worth
a mock; cover instead the option parsing (0, 1024, 1025 → 422, non-integer →
422) and `usage.output_tokens` in the response writer.

Model-backed: N = 0 equals `800` bitwise; N = 64 twice gives equal logits and
equal `think_tokens`; a context-overflow request is refused before
evaluation.
