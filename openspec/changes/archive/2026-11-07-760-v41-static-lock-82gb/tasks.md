# Tasks

## 1. Evidence (2026-11-07, probe build in the scratchpad)

- [x] 1.1 Full-file-cache gap located: GPU waits of about 290 ms per command batch between commit and completion, GPU time unchanged; explicit-buffer allocation ruled out (205-238 ms in both states)
- [x] 1.2 Forced static lock: full file cache 15.6-15.7 -> 12.7 s, warm unchanged; README sweep back to back, first 2048 tokens 169.5-175.6 -> 179.8-181.7 t/s, the rest within 1%; peak wired 103.6 GiB (32K), 105.66 GiB (256K, copy, `--boost`)

## 2. Implementation

Implementation state on the night of 2026-11-07:
- Built and tested in a scratch copy of the `750` tree, not in a worktree.
- The patch against `750` is `.claude/worktrees/760-static-lock-82gb.patch`
  (`ds4.c` only).
- `make test` passes. The logits at 2048 and 8192 are byte-identical with and
  without the switch.
- The loader decides "98.77 GiB planned wired against the 108.80 GiB user wire
  limit less 6 GiB: lock" at 32K, and 101.26 GiB at 256K.

- [x] 2.1 Read `vm.global_user_wire_limit` (`sysctlbyname`) at engine open; lock the statics when the planned wired total plus the transient margin fits under it, as a second path next to the 7/8 budget; print which path decided
- [x] 2.2 `make test`; bench logits at 2048 and 8192 byte-identical with and without `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK`

## 3. Measurement

- [x] 3.1 `750`'s full and warm states (root-free start state), lock against `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK=1`
- [x] 3.2 Harness A/B against `main`+`750`: `decode`, `append`, `cold-2500,cold-7500`
- [x] 3.3 256K sessions (bench, 245760 tokens, the copy, `--boost`) at `82GB` and `80GB`: locked, every slot locked ahead, peak wired 102.42 and 99.55 GiB (`memsample.py`); logits byte-identical with and without the lock on the landing tree
- [x] 3.4 `750`'s server test: request B pages in no static weight

## 4. Docs

- [x] 4.1 `AGENTS.md` (SSD streaming: the lock decision at `82GB`), `speed-bench/perf-record.md`; README tables re-measured on `main` after landing, at `80GB`
