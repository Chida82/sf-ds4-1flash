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

### D5. Binding point (task 1.1, 2026-10-06)

Read in ds4 at `0aaea5a`; branch `dual-ssd-prefill-v41` in `~/github/chida82/ds4`.

- **GPU side.** In a wide V4.1 sweep the routed MoE runs `ds4_gpu_routed_moe_batch_tensor`, and on its non-cached branch it resolves gate, up and down with `ds4_gpu_wrap_model_range(model_map, ...)` (`ds4_metal.m`). That function looks the range up among the registered model views by `(model_map, offset)`, and under SSD streaming `ds4_gpu_set_model_map_spans` replaces only the views of the map it is given. So a second map can coexist with the model's:
  - the sweep registers the layer's up range from the copy's mapping next to the model's layer spans;
  - a setter, `ds4_gpu_set_prefill_up_map`, makes that one `wrap` call resolve up from the copy;
  - the sweep sets it per layer and clears it before decode.

  The small-batch paths (selected-address and cached) keep the model, and so do decode and the single-token MoE.
- **Page-in side.** The sweep's layer page-in (`metal_graph_stream_prefill_layer_pagein_start`, `pread_only`) splits each span evenly over 8 workers, and every worker `pread`s from `model->fd`. With a copy:
  - workers 0-2 read the layer's up from the copy's fd;
  - workers 3-7 read the rest from the model in contiguous byte shares, as `140`'s 3-of-8 split does, so both drives have requests in flight;
  - `pread_range` takes the fd as a parameter.
- **Open.** `ds4_engine_open` opens and checks the copy as `140` does, right after `ds4_gpu_set_ssd_streaming`, for V4.1 only:
  - the header and every layer's routed up are compared through uncached descriptors;
  - the copy must be a different inode with the same size.

  Caching is then turned back on for the copy, and it is mmapped read-only. A change after the check stops the next sweep.

Diff: about 280 lines, almost all in V4.1 prefill code:
- `ds4.c`: about 270 lines;
- `ds4_metal.m`: 7 lines;
- `ds4_gpu.h`: 3 lines.

The only shared-code touches are the fd parameter of `pread_range` and the map choice in one `wrap` call, which uses the model unless the V4.1 sweep has set the copy. Not invasive: go.

## Risks / Trade-offs

- [ds4's Metal model map may assume one mapping per model] -> a second mapping for the up ranges only. If that touches too much shared code, stop and report before widening.
- [mmap page faults on the copy are slower than pread into a locked buffer] -> D3 measures it; a small gain is still a valid answer.
- [Upstream moves on] -> the branch stays on `0aaea5a` for the measurement; rebasing for a PR is a separate step.
