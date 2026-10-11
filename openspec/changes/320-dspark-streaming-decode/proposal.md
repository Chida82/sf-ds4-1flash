# Proposal

## Why

This change starts only when `310`'s gate says go. It brings V4.1's own drafter into this child and makes it run under SSD streaming, the child's only mode. The aim is a faster single request on content the drafter predicts well, such as code, agents and tool calls. It is opt-in, and greedy output stays the same.

The work exists as a resident-only implementation in open PR #1073, which owns this code zone. This change ports it and adds the one thing it lacks: verify rows that read their experts through the streaming cache.

## What Changes

- **Harness, tool step.** `speed-bench/ab_bench.py` gets a `decode-code` kind: a code prompt file in `speed-bench/`, frontiers 2048 then 8192, and 256 generated tokens. The typical mix stays on prose. The candidate gets the drafter through the existing `--b-bench-arg`, so A is plain decode, B drafts, and the token gate compares them.
- **Speculative decoding, back in this child, V4.1 only.** From #1073's head:
  - the support-GGUF loader (`ds4_dspark_weights`, its metadata check);
  - the drafter (`ds41_draft_*`: capture, rings, proposal, verify, rollback);
  - the session cycle (`ds41_session_spec` behind `ds4_session_eval_speculative*`);
  - the confidence-selected draft length and the back-off (`ds41_draft_adapt`).

  The V4 Flash DSpark engine and the TP spec cycles stay deleted.
- **Under streaming.**
  - The `g->streaming` gate goes.
  - Verify rows route per row, and their experts are read through the cache as one union per layer, with the misses loaded before the layer's MoE.
  - Only kernels whose rows are bit-identical to one-row decode are taken: `310`'s configuration. The MMA rows (`262b4a6`, `a6b50ff`) stay `drop: output`.
- **Flags** in the CLI and the bench, under upstream's names:
  - `--dspark`;
  - `--mtp-model FILE`;
  - `--dspark-confidence X`.

  The default cap and threshold come from `310`. At non-zero temperature this change does not draft and says so once; `340` adds exact sampling.
- **The file.** `download.sh` gets a DSpark component for the file `310` chose, with a symlink in `gguf/`.
- **Documentation.**
  - The child's `AGENTS.md`: the section "Speculative decoding: none" is rewritten, and the identity row updated.
  - `README.md`: a section on the flag, its memory and its expected gains per content kind.
  - `docs/upstream-prs.md`: the DSpark commit lines set to `adopt -> 320`.
- **The orchestrator registry** (StarForge `AGENTS.md`, `README.md`, `tools/lib.sh`, `tools/parity/sf-ds4-1flash.txt`) changes from "none" to "DSpark (V4.1 drafter, opt-in, streaming)". This is a separate StarForge commit, made on request, because rule 6 binds the child to it.

## Capabilities

### New Capabilities
- `dspark-drafting`: opt-in speculative decoding with V4.1's DSpark drafter under SSD streaming. It covers the flags and the support file, output identity, the per-cycle draft length, back-off, and the refusals.

### Modified Capabilities
- `perf-harness`: a decode kind on code content.

## Impact

- **Engine.**
  - `ds4.c`: loader, drafter, session cycle, the speculative API for V4.1.
  - `ds4.h`: a narrow API.
  - `ds4_metal.m` and `metal/*.metal`: the rows > 1 forms of the decode kernels, plus the union lookup for verify rows.
- **Frontends and tests.** `ds4_cli.c`, `ds4_bench.c`, `tests/`.
- **Files and docs.** `download.sh`, `README.md`, `AGENTS.md`, `docs/upstream-prs.md`, `speed-bench/`.
- **Memory.** The drafter is resident beside the `82GB` cache: 7.42 GiB at MXFP4, or `310`'s choice.
- **Sync cost.** It is lowest while #1073 is followed as written. If upstream merges #1073, the zone merges with few conflicts. If upstream drops it, the zone becomes this child's to keep.
