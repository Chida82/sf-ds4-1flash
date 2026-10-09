# Design

## Context

`ds41_prefill_replica_open` (`ds4.c`) refuses anything but single-box Metal streaming with the Q2 experts, opens the copy with `F_NOCACHE` and `F_RDAHEAD 0`, and runs `ds41_prefill_replica_check` over the header and each layer's routed up range. It then stores the copy's size and mtime in the model. `ds41_prefill_replica_unchanged` compares them with `fstat` before every explicit layer read; a change stops the prefill with an error.

## Goals / Non-Goals

**Goals:** skip the full comparison when neither file has changed since it last passed; never admit a copy the full comparison would refuse in the same state.

**Non-Goals:** content hashing (the comparison is the hash); verifying the model file itself; changing the per-layer check; the decode use of the copy (`260`).

## Decisions

### D1. What the stamp binds

Both files' `st_dev`, `st_ino`, `st_size` and `st_mtimespec`, plus the total bytes of the compared ranges and a version. A rewritten file changes the mtime; a different file changes the inode; a moved copy keeps the inode on the same volume, which is the same bytes. The model's fields guard against a new model with the same copy, the ranges total against a GGUF with another layout.

Alternative, a content hash stored in the attribute: it costs the same read as the comparison, so it saves nothing.

### D2. Where it lives

An extended attribute on the copy (`setxattr`/`getxattr`, `XATTR_NOFOLLOW`), not a sidecar file: it travels with the file, disappears when the file is replaced, and needs no directory write. On a filesystem that refuses it (`ENOTSUP`, `EROFS`, `EPERM`) the open behaves as today.

### D3. Write after a pass, never before

The attribute is written only after a full comparison returns equal. A failed comparison removes any existing attribute before the refusal is printed.

### D4. Mtime trust

A tool that rewrites bytes and restores the mtime (`touch -r`, some copy tools) would pass the stamp with different content. The per-layer check has the same blind spot today. `DS4_METAL_PREFILL_REPLICA_FULL_CHECK=1` and the documentation cover it: after copying the GGUF again, run once with the full check, or remove the attribute with `xattr -d`.

### D5. Evidence

- `make test-deepseek41-prefill-replica REPLICA=<path>` extended: first open writes the stamp; second open skips and prints so; `touch` on the copy forces the full check; a copy truncated by one page is refused; the forced full check runs with a valid stamp.
- Timing of two consecutive CLI opens with the copy, before and after.

## Risks / Trade-offs

- Mtime-preserving rewrites -> D4.
- A volume mounted read-only -> no stamp, full check every time, as today.
- Two engines opening at once -> both may write the same attribute; the value is identical, last writer wins.

## Migration Plan

Branch `sf/280-replica-check-stamp` from `main`; independent of `250` and `260`. No commit or push without a request.
