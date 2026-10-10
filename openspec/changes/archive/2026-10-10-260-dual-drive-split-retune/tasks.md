# Tasks

## 1. Gate

- [x] 1.1 Run `missbench` and `enginebench` (scratchpad) on the copy as ExFAT and as APFS, two runs each, the same night. Verify each run reports its resampled count. Record both tables in `speed-bench/perf-record.md` with the verdict per mode: does up from the copy, whole or in pieces, end before the internal drive's gate/down?
  - Done 2026-10-10. Both probes evict the sampled ranges first (`msync(MS_INVALIDATE)`), because the first ExFAT runs read the internal side partly from the page cache. ExFAT and APFS agree within 1%: one miss 0.96 -> 0.67-0.73 ms with up from the copy. Pieces alone 0.95. Moving `F_RDADVISE` into the tasks, or dropping it, changes nothing.

## 2. Code

- [x] 2.1 D1-D4: the pieces switch, the copy's cached descriptor, the per-task source, advice on the reading descriptor, the change check and the last-landing counters. Verify `make` and `make test` (output names the tests); `make test-deepseek41-decode-switch` with `SWITCH=DS4_METAL_V41_DECODE_PIECES` and with `SWITCH=DS4_METAL_V41_DECODE_REPLICA_UP` under `DS4_METAL_PREFILL_REPLICA=<copy>`, bitwise; `make test-deepseek41-prefill-replica REPLICA=<copy>`.
  - Done 2026-10-10 with the copy on ExFAT. The build has no warnings, and `make test` passed with the V4.1 expert-read lines named.
  - Both switches gave 65 exact logits/history/KV states at prefixes 511 and 2047. The prefill replica test passed.

## 3. Harness on both file systems

- [x] 3.1 On the drive's current file system: harness `decode,append`, `--bitwise`, 3600 s, `--env DS4_METAL_PREFILL_REPLICA=<copy>`, with B = pieces, B = up from the copy, and B = both. Verify bitwise. Record the rows and the last-landing counts from a single run with the timing summary.
  - Done on ExFAT 2026-10-10, 24 pairs each, bitwise. Decode 2048 / 8192: up +0.2% / +0.3%, both +0.2% / +0.2%, pieces -0.2% / -0.7%, all CIs across zero. In the engine, prepare grows 0.06-0.12 ms per miss layer while the read shrinks 0.03-0.15 ms.
- [x] 3.2 Reformat the drive to the other file system, copy the GGUF and `cmp` it, then repeat the two copy steps of 3.1. Verify bitwise. Record the rows.
  - 2026-10-10: reformatted to APFS, copied and `cmp`-checked. The drive dropped during the up single run at 10:26 (the read failed, decode stopped cleanly) and came back after a replug. Up on APFS ran after the replug, 24 pairs, Heavy, bitwise: decode 2048 +0.1% (-0.8..+6.2), decode 8192 +0.0% (-0.9..+1.3). Both was not run, since pieces did nothing on ExFAT and the probes match across file systems.

## 4. Decision and integration

- [x] 4.1 Apply the keep rule per step and per file system. Write in `speed-bench/perf-record.md` which file system gives the larger total, with this change's decode gain and `250`'s first-token gap. Add a Rejected-ideas row for each dropped step.
  - Done 2026-10-10. No step is kept on either file system. The file system choice does not depend on this change. `perf-record.md` has Decode misses split across drives after 250, the `145` Rejected-ideas row is extended, and a pieces row is added.
- [x] 4.2 For a kept step:
  - review against `AGENT.md`;
  - fix `AGENTS.md`'s sentence on decode reads (no split in decode today, or the new switch);
  - document the switches, the README's second-drive section and `docs/upstream-prs.md`;
  - `make`, `make cpu`, `make test`, the model-backed checks and the parity oracle;
  - `openspec validate 260-dual-drive-split-retune --strict`.

  No commit or push without a request.
  - No step kept. The switches and the second descriptor stay out of `main`. `AGENTS.md`'s decode read sentence was wrong regardless, and is corrected.
