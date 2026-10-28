# Design

## Context

`close2` (change 419) is `sf-ds4-1flash-candor` with one addition: the two-stage closure
object in the `.sfsteer` header plus the embedded satisfied-closure matrix. The slots are
identical (same equi/q1 vectors, scales, phases and 418-C decay). Promotion is therefore a
rebuild of the shipped profile, not a new mechanism — the engine, loader and tooling
already shipped in 419.

## Goals / Non-Goals

- Goal: callers of the default `sf-ds4-1flash-candor` get loop-breaking in think, with the
  non-think and answer phases unchanged.
- Non-Goal: no engine, kernel, Makefile or binary change; no change to the fold slots; no
  change to `close0.25` / `close0.5` / `close2` (kept as named alternatives).

## Decisions

1. **Rebuild in place, keep the internal name.** Rebuild `sf-ds4-1flash-candor.sfsteer`
   with `make_profile.py` using the current candor slots plus `--closure`/`--closure2`
   with close2's parameters, `--name sf-ds4-1flash-candor`. The file path and the loaded
   profile name do not change, so every doc, test and call site that names the default
   keeps working. (Alternative — ship close2 under the candor name by copying bytes —
   rejected: the name field inside the header would read `...-close2`, and provenance
   should be rebuilt, not renamed.)

2. **Re-pin, do not hand-edit.** Regenerate the slot/closure hashes, scales, phases,
   schedule and accepting run ids into `sf-ds4-1flash-candor.json` from the rebuilt file,
   so the pin matches the bytes.

3. **Reuse 419's evidence; add one identity check, not a fresh sweep.** The think verdict
   (41.0 `C41 R3`, loop 3/44), the non-think guard (44/44 byte-identical) and the benign
   gate (16/20 byte-identical, both benign loops repaired) were measured on close2 in 419
   and apply unchanged, because the promoted candor is byte-for-byte the same profile under
   a different name. The only new check needed is that the rebuilt-as-candor file is
   byte-identical to the already-measured close2 **matrices** and carries the same closure
   schedule — a file-level diff, no GPU. The think-level still arrives from the frontend
   (unknown = 75).

4. **Docs follow the profile.** Update the think figure wherever it is quoted
   (`com-steering/README.md`, `com-steering/result.md` / `kpi.md`, and the `AGENTS.md`
   identity note only if it states a think number) from 39.0 / loop 13/44 to 41.0 / loop
   3/44, and state that non-think is unchanged.

## Risks / Trade-offs

- **The default now shortens some benign long thoughts.** The benign gate showed one
  benign reasoning out of twenty closed ~940 tokens earlier (and repaired two benign
  loops). This is the documented cost of the ~3000-token onset and is accepted; it rides
  on the default now rather than being opt-in. Recorded in `investigation.md`.
- **Parity oracle.** The StarForge parity oracle compares upstream vs this fork on
  `parity_prompts.txt` without steering, so a profile swap does not move it; it is run as
  the standard pre-PR gate, not as evidence for this change.
