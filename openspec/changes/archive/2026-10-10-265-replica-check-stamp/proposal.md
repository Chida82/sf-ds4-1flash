# Proposal

## Why

Every engine open with `DS4_METAL_PREFILL_REPLICA` compares the header and the 43.51 GiB of routed up between the model and the copy: about 7 s with the copy on the TB5 drive. A server pays it once; the CLI, `ds4_test`, and every harness run pay it at each start. When neither file has changed since the last full comparison, the result is already known.

The copy can carry its own verification record as an extended attribute. APFS stores it natively; on ExFAT macOS keeps it in a `._` AppleDouble file next to the copy (checked 2026-10-09: written and read back). If that file is lost, for example after a copy made outside macOS, the stamp is missing and the full comparison runs.

The check inside a prefill stays as it is: one `fstat` per layer read (size and mtime), about 1 us, 40 times per sweep. It is what keeps a copy rewritten while the engine runs from feeding different bytes to the prefill, and the stamp below relies on it.

## What Changes

- After a full comparison passes, the engine writes an extended attribute on the copy, `com.starforge.sf-ds4-1flash.replica`. It records the copy's device, inode, size and mtime, the model's device, inode, size and mtime, the compared ranges' total, and a format version.
- At the next open, if the attribute exists and every recorded field matches both files' current `fstat`, the full comparison is skipped and the copy is admitted. The open prints `replica check: stamp matches, comparison skipped`.
- Any mismatch, a missing attribute, a read-only volume, or a filesystem without extended attributes means the full comparison runs as today, then the stamp is rewritten.
- `DS4_METAL_PREFILL_REPLICA_FULL_CHECK=1` forces the full comparison.
- The per-layer `fstat` check is unchanged.
- Output is unchanged: the same copy is admitted in the same cases.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: `ds41_prefill_replica_open` (read and write the attribute around `ds41_prefill_replica_check`).
- `AGENTS.md` replica paragraph and `README.md` second-drive section (the 7 s note); `tests/` replica target extended with a stamp case.
- About 7 s saved per engine open after the first. No throughput change.
