# Proposal

## Why

A decision's cost here is dominated by the state: 6-7 s for one sweep of
256-2000 tokens, against about 1 s per question (`docs/system-one.md`,
section 3). The callers System One is made for ask about the same state again
and again: an agent loop that checks "is the task done?" after each step, a
guardrail that screens the same conversation as it grows, a router that asks a
second question depending on the first answer. Today each request prefills the
state from scratch, and it also throws away the live KV of the chat session
that shares the slot, so the next chat turn pays a full prefill too.

Rizzo Flow shares the state only inside one request. A cache across requests
is the first thing this model's cost profile asks for.

## What Changes

- A small in-memory cache of state snapshots in the server, keyed by the
  state prefix tokens. A request whose state prefix equals a cached one
  restores it and pays only its question suffixes. A request whose state
  prefix *extends* a cached one restores it and prefills only the new part.
- The chat session's live state is saved before a decision and restored after
  it, so a decision between two chat turns costs the chat nothing.
- Flags `--sysone-state-cache N` (entries, default 4, 0 disables) and
  `--sysone-state-cache-mb M` (byte budget, default 2048).
- The bench gains a `repeat` scenario and records the snapshot cost at 2K, 8K
  and 32K tokens of state.

## Non-goals

- No disk persistence of state snapshots (the server is long-lived; the disk
  KV store is keyed by rendered chat text and stays the chat's).
- No sharing between slots beyond the cache itself.
- No partial "journal" restore; it is designed here only as a fallback if the
  measured restore time is too high.

## Impact

- `ds4_server.c`: the cache, the save/restore around `sysone_job`, the flags.
- `sf_sysone.c`: `sf_sysone_decide` gains an optional prepared-state path.
- `sysone-bench/run.py`: the `repeat` scenario.
- Docs: `docs/SERVER.md`, `docs/system-one.md`.
