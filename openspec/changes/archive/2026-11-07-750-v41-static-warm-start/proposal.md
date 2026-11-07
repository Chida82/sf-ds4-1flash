# Proposal

## Why

In SSD streaming, the static weights (9.4 GiB: attention, shared experts,
norms, router, Engram and indexer projections) stay pageable at the `82GB`
cache, because they do not fit next to the expert cache. Whether they are in the
file cache when a prefill starts decides its speed. On 2026-11-06 the first
2048-token prefill of a fresh process ran at 161.8 t/s with the static weights
cached and at 117.2 t/s with them cold (`sudo purge` before the run), with or
without the narrow decode copies (161.0 and 116.5 t/s). With the same start state
the copies cost nothing. In back-to-back runs they seemed to cost 17%
(135-145 against 165-172 t/s). The cause is that the engine open wires about
74 GiB and the kernel evicts the oldest file pages. A previous process whose
decode reads the narrow copies never touched the wide weights they replace
(router F32, Engram projection F16, indexer q_b F16: 0.96 GiB), so these go
first, and the next prefill pages them back in: up to 1.4 GiB and 13 s of fault
waits (`fs_usage`). The README's prefill row and every fresh-process
measurement depend on this start state. Whether a long-lived server meets the
same faults has not been measured.

## What Changes

- Measure the server regime first: one long-lived process, a prompt and a long
  generation, then a new prompt. Count the static-weight page-ins of the second
  prefill (`fs_usage`, page-cache snapshots), with the narrow copies on and off,
  and with other file I/O between the two requests.
- Make the first prefill independent of the inherited file cache: after the
  expert cache is locked at engine open, bring the static weights into memory
  before the first prefill (prefault). A switch turns it off.
- If the server regime does page the wide weights back in, also keep the wide
  weights the decode skips resident while their narrow copies exist (locked,
  0.96 GiB, taken out of the cache target like the copies). A switch turns it
  off.
- Record the start-state dependence in `speed-bench/README.md` and
  `perf-record.md`: what a fresh-process run measures, and which state the
  README tables assume.

## Capabilities

### New Capabilities
- `static-weight-residency`: whether the static weights are in memory when a
  prefill starts, at engine open and in a long-lived process, and the switches
  that turn the residency measures off.

### Modified Capabilities
None.

## Impact

- Code: `ds4.c` (engine open after the expert-cache lock-ahead; the narrow-copy
  reservation if the wide weights are locked), `ds4_env.def` (the new
  switches).
- Memory: the prefault adds no wired memory. Locking the wide weights would take
  0.96 GiB out of the expert-cache target (about 103 of 8026 slots).
- Docs: `AGENTS.md` (SSD streaming section), `speed-bench/README.md`,
  `speed-bench/perf-record.md`.
- Output: unchanged, bitwise. Only the residency of weights changes.
