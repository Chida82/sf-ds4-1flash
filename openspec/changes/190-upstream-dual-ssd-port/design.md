# Design

## Context

See proposal.md.

In ds4 at `0aaea5a`:
- `metal_graph_stream_prepare_start_if_needed` starts page-in workers that `pread` each layer's expert ranges from `model->fd` into a scratch buffer, only to warm the page cache;
- the Metal model map wraps the model's mmap as no-copy buffers, and the kernels read the experts from those pages.

Reading up from a copy with `pread` would warm the copy's pages, not the model's, and the GPU would still fault the model's pages from the internal drive.

## Goals / Non-Goals

**Goals:** the smallest ds4 change that lets a second drive deliver part of the prefill expert bytes, its measured gain on V4.1 Flash, and a branch suitable for review.

**Non-Goals (before A's numbers):**
- Porting this child's explicit buffers, wide-sweep schedule or `145`'s decode change.
- Other models.
- Decode reads from the copy (`145` measured -1.7% here).

## Decisions

### D1. Map the copy and bind up from it

At engine open, when the opt-in names a copy:
- open and validate it as `140` does (the header and the routed up ranges byte-for-byte, a different inode, the same size);
- mmap it read-only;
- register the up tensor ranges with Metal from the copy's mapping.

The bytes are identical, so the kernels and the output are unchanged.

During prefill page-in, the workers `pread` up ranges from the copy's fd and gate/down from the model's fd. Each warms the pages the GPU will actually read, on its own drive, concurrently.

Decode keeps reading the model. Decode cache misses then copy from the model's pages, so whether decode binds up through the model or the copy must be settled in the code. Reads stay on the internal drive for decode, which `145` measured.

### D2. Validation and failure

Same contract as `140`:
- an invalid copy refuses to start, with a reason;
- a change after admission fails the next prefill;
- bounded parallel comparison;
- startup cost reported.

Reuse `140`'s code where it fits ds4's structure, with attribution in the commit message, never in source comments.

### D3. Measurement

Use the ds4 bench (as in `tools/speed-compare.sh` and the `0aaea5a` worktree): `--ssd-streaming --ssd-streaming-cache-experts 82GB --ctx-alloc 32768`, frontiers 2500, 3500, 5000, 7500, 10000 and an append shape, and decode 2048/8192, in alternated runs. Original ds4 and the port run on the same GGUF and copy, with greedy output compared token for token.

Report per shape the median gain with its spread. Record it here, and add a `docs/upstream-prs.md` line.

### D4. Nice to have, gated on D3

Only after D3, and each on the owner's decision:
- port `60`/`100`'s explicit buffers, then `140` unchanged, measured against D1's port;
- any other second-drive item.

A combined diff is larger and less likely to be accepted upstream. The D3 numbers decide whether it is worth offering.

## Risks / Trade-offs

- [ds4's Metal model map may assume one mapping per model] -> a second mapping for the up ranges only. If that touches too much shared code, stop and report before widening.
- [mmap page faults on the copy are slower than pread into a locked buffer] -> D3 measures it; a small gain is still a valid answer.
- [Upstream moves on] -> the branch stays on `0aaea5a` for the measurement; rebasing for a PR is a separate step.
