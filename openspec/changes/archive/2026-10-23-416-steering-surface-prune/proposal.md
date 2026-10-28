# Proposal

## Why

The steering exploration left behind a large surface that no longer serves it.
Six runtime probes were built to answer questions that are now answered, and the
harness grew 24 one-off scripts and several gigabytes of stored arms around a
single comparison. Two of those probes are still described by landed
requirements, so the specs now claim behaviour the engine does not have.

Keeping an unused probe is not free here: every switch must stay classified in
`ds4_env.def`, every kernel argument is a line upstream does not have and a
conflict at the next sync, and a reader cannot tell a live lever from a dead
one. The exploration's findings are kept; its scaffolding is not.

## What Changes

**Engine probes removed.** The closed-loop per-token scale controller
(`DS4_DIR_STEERING_CONTROL` and its `_DEBUG`, `_PUSH`, `_THINK_ONLY` companions),
the decay and cyclic scale schedules and their five flags, the probe-dosed second
slot (`--dir-steering-probe-2`), the fold activation capture
(`DS4_V41_DUMP_STEER_INPUT`), the prefill/decode phase ablation
(`DS4_STEERING_PHASE`) and the CLI's `--perplexity-dump`. Seven names leave
`ds4_env.def`.

**The Metal side returns to upstream.** `ds4_metal.m`, `metal/dsv4_misc.metal`
and `ds4_gpu.h` are byte-identical to `main` again: the readback buffer, the
probe buffer and the extra kernel argument they needed are gone, so the steering
kernel is upstream's with no local delta.

**Harness reduced to what runs.** `eval/` keeps the ten modules `run.py`
imports; the 24 one-off run scripts, the stored arms and the two lab documents
go. The vectors the measurements refer to, and the profile they produced, move
to `com-steering/`.

**Steering tests removed, including tests of live behaviour.** The steering
additions to `tests/test_deepseek41_graph.c` go, with
`tests/test_steering_admission.py` and the three model-backed `make` targets.
This is the one part of the prune that removes verification rather than dead
code: the fold's route-agreement check, the rank-2 off-path check and the
admission check covered behaviour that is still live. Recorded here as a
deliberate choice, not an oversight, so that a later reader knows the fold has
no automated oracle.

**Specs corrected.** The two requirements describing the removed capture and the
removed extractor are dropped from `directional-steering`.

## Non-goals

This change removes no *live* steering behaviour: the fold, the opt-in, the
rank-2 second direction, the loader validation and the persistence guards are
untouched, and the phase gate and profiles of `417` build on them. It does not
decide the fate of `eval/` itself, which stays.

## Evidence

Unsteered output is unchanged: the ten parity prompts plus one reasoning prompt
generate byte-identical text against `main`. Steered output is unchanged: the
same prompt under the same configuration is byte-identical to the pre-prune
binary, in both reasoning and non-reasoning mode. `make test` passes.
