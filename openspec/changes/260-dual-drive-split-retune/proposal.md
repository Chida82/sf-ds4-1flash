# Proposal

## Why

With one external drive, the Argodrive fork measured steady decode at 18.66 tok/s on the internal SSD alone, 21.05 with one enclosure (+12.8%) and 22.25 with two (drive ladder of 2026-09-27, V4.1 Q4, pp512). Most of the gain comes from the first external drive. Their decode reads split each miss across the drives by weight (`DS4_ARGODRIVE_DECODE_WEIGHTS`, primary first, about 10:6 per drive), with a separate weighting for prefill, tuned by recording which drive's piece landed last.

Here the same idea measured -1.7% on decode (`145`), because the copy, then on ExFAT, had a floor of 0.6-0.7 ms per 2-3 MiB read. If `250` shows that floor gone on APFS, two splits are worth tuning on a box with one external drive:

- **Decode misses.** 4.0 miss layers per token, `pread` 0.667 ms each: about 7% of a token. A miss read in parallel from both drives can save up to about a third of it, about 2-2.5% of decode. The Q4 gain does not transfer one to one: a Q4 miss is larger and more bandwidth-bound.
- **Prefill.** `140` reads `up` from the copy on 3 of 8 readers, a share chosen on ExFAT. It measured ttft +10-17% and append +1500 +17%. A share retuned on APFS can only move that up or leave it.

## What Changes

- **Gate: `250` task 1.1.** If the copy's piece median is not below the internal drive's for the rest of the expert, the decode part closes with no code, and only the prefill sweep runs.
- **Decode split (S1).** The pread pool sends a configurable share of each miss's pieces to a second descriptor on the copy: k of the 16 KiB-aligned pieces (4 per family, 12 per expert), chosen from the gate's table. It requires the copy admitted and verified by `140`'s check, applies only to single-box streaming decode, and sits behind `DS4_METAL_V41_DECODE_REPLICA_SPLIT=<k>`, read per load. The streaming summary counts, per drive, how many times its piece landed last.
- **Prefill share (S2).** The explicit buffers' reader assignment gets an override, `DS4_METAL_PREFILL_REPLICA_READERS=<n>`, the readers out of 8 that read from the copy (today 3, `up` only), and optionally gate. It is swept at 3/4/5 and kept only with a CI above zero on ttft.
- Output is unchanged by construction: the same bytes land in the same slots. Every run is `--bitwise`.
- Expected: decode +0-2.5% (gate-dependent), prefill +0-5% on top of `140`.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: the copy's descriptor in the pool, the per-piece choice, last-landing counters.
- `ds4.c`: the copy's fd handed to the Metal side when admitted; the reader-share override in the explicit buffers.
- `AGENTS.md` ("SSD streaming is not optional", replica paragraph and switches), the README's second-drive section, `docs/upstream-prs.md` ("Ideas from other forks", `DS4_ARGODRIVE_DECODE_WEIGHTS`), `speed-bench/perf-record.md`.
- Needs the external drive for every measurement. Without the copy admitted nothing changes.
