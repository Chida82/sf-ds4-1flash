# Proposal

## Why

Two steering behaviours are live in the engine and described by no requirement.

The first is the **reasoning-phase gate**. The measurements showed that the two
phases want different doses: a second direction that *hurts* when applied
everywhere becomes useful when it is confined to the reasoning, and the primary
direction has to stay in both. Without a gate that configuration cannot be
expressed at all.

The second is the **steering profile**. A working configuration was five flags
and an environment variable, in an order that had to be remembered, with two raw
`.f32` files whose identity nothing recorded. That is too much surface for the
one thing an operator actually wants to say: *use this configuration*.

## What Changes

- **Per-slot phase gate.** `DS4_STEERING_THINK_PHASE` and
  `DS4_STEERING_THINK_PHASE2` confine slot 1 and slot 2 to the reasoning or the
  answer phase, keyed on the `</think>` boundary. Default is both phases, which
  is the existing path unchanged.
- **Gated sessions decode serially.** One native batch forward folds every row
  with one graph's scale, and a gate is per session, so a gated session cannot
  share a batch. It takes the serialized path instead.
- **Steering profile.** `--steering-profile NAME|FILE` loads a whole
  configuration — both directions, their scales and their gates — from one
  `.sfsteer` file. A bare name resolves under `com-steering/profiles`. The
  profile is itself the V4.1 opt-in and replaces the `--dir-steering-*` options
  rather than combining with them.
- **The file carries its own provenance.** The JSON header records the profile
  name, a description and the SHA-256 of each matrix it holds. The engine
  ignores those fields; they exist so a file found later can be identified.

## Non-goals

The gate does not change the fold, the site, the rank-2 composition or the
persistence guards. A profile expresses only what the flags could already
express: it adds no new steering behaviour, and a profile run and the equivalent
flag run produce identical output.

## Evidence

A profile run, the equivalent raw-flag run, and the same raw-flag run on the
binary from before the prune all produce byte-identical text, in both reasoning
and non-reasoning mode; the same prompt without steering differs, so the edit is
really applied. Recorded 2026-10-23 on the 1017 checkpoint.

**These requirements have no automated test.** The model-less steering tests
were removed in `416`, including the one that covered the profile parser. The
evidence above is a one-off model-backed comparison, not a check that runs
again. Restoring an oracle is open work.
