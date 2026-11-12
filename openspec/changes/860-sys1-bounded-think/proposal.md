# Proposal

## Why

A pure System One answer uses none of this model's reasoning, and the model's
own System 2 costs a median of 600-2200 thinking tokens (20-70 s,
`docs/MODEL_KNOWLEDGE.md`). Nothing sits in between, and no surveyed system
offers a middle: their models are 0.3-9B and cannot think.

Here the middle is cheap to build. `</think>` is a token; a session can
generate N reasoning tokens greedily, be handed `</think>` whether or not it
was about to stop, and then be read exactly as in `800`. N is a dial: 0 is
System One, 64 costs 2 s, and the natural stop is full System 2 with a typed,
probabilistic answer instead of parsed text.

`820` measures the System One gap. This change is proposed for the case where
that gap is above 5 points on some question family; below that, record the
gap and skip the change.

Whether a *forced* close works is unknown: `docs/MODEL_KNOWLEDGE.md` records
that the base model's `</think>` logit gap is about 22 until ten tokens before
its natural exit, so a forced close lands where the model did not expect one.
The first step measures that before anything is built on it.

## What Changes

- Request option `"sf":{"think_tokens":N}` (0-1024, default 0) and
  `"sf":{"think_effort":L}` (reasoning effort level 1-100, default 25).
- Per question: thinking opened, up to N greedy tokens, `</think>` forced if
  the model has not closed, the answer prefill, the readout.
- `usage.output_tokens` reports the thinking tokens generated.
- A bench curve: accuracy, ECE and latency at N = 0, 32, 64, 128, 256 and at
  the natural stop.
- Second stage, only if `840` was kept: **think once, answer many** — one
  shared reasoning pass over the state and all question definitions, then the
  pointer readouts.

## Non-goals

- The thinking text is not returned (a decision API returns no text); with
  `sf.debug` it is returned for inspection.
- No sampling: thinking is greedy, so a decision stays deterministic.
- No steering: decisions stay unsteered.

## Impact

- `sf_sysone.c/.h`: the think path. Engine sources untouched.
- `ds4_server.c`: options, usage, boost untouched.
- Bench: `--sf` sweeps and the record.
