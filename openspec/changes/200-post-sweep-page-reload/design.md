# Design

## Context

See proposal.md. At engine open, `ds4_engine_open_internal` locks the decode static spans only when they fit next to the expert cache and the prefill headroom (`ds4_streaming_manual_cache_safe_bytes`). With the 82GB cache flag they do not fit: about 9.4 GiB stay pageable.

During an explicit-buffer sweep the engine adds pressure:
- the two layer buffers lock about 7 GiB;
- `pread` delivers about 3.8 GB per layer;
- Engram rows and the seeds run alongside.

At the end it frees the buffers and maps the decode statics again (`metal_graph_stream_map_decode_static_all`). `180` measured memory use climbing about 8 GiB right after the sweep, over 1.2 s without the copy and 0.5 s with it.

## Goals / Non-Goals

**Goals:** a first token after a sweep that does not wait for the drive, and the same for ttft shapes with a token-by-token tail, with bitwise output.

**Non-Goals:**
- Changing the expert cache size.
- Changing the prefill schedule or kernels.
- A second-drive requirement.

## Decisions

### D1. Gate

A probe build, never landed, records `mincore` residency of every decode static span:
- after the previous decode;
- at each tenth layer of the sweep;
- at its end;
- after the first token.

It also records `vm_stat` page-ins, per harness shape: `cold-2500`, `cold-5000`, `cold-10000`, `append`, and decode 2048/8192 with 256 tokens. Run with and without the copy.

**Go** if the static spans are the pages reloaded and the reload costs more than the harness resolution on a target metric: the first token after the sweep, or ttft for shapes with a tail. **Stop otherwise**, with the figures and a Rejected-ideas row if a fix was tried.

### D2. S1, re-warm in the background

From the sweep's last layers (for example from layer 36), hand the static spans to a background reader that brings them back:
- `madvise(WILLNEED)`, or touching one byte per page;
- bounded, and joined before the sweep returns, so no stray thread outlives it.

It reads at most what was evicted (`mincore` decides, so a resident span costs nothing) and overlaps with the GPU's last layers. It must not delay the sweep's own reads: start after the last layer's experts have been read.

### D3. S2, keep them resident

Only if S1 cannot hide the reload. Options:
- lock the static spans for the duration of decode only, unlocking them during a sweep, which needs no new admission;
- extend the lock decision so the statics fit by counting the explicit buffers' reserve once.

Any change to admitted memory is shown to the owner with the before and after figures first.

### D4. S3, steady decode with the copy

If the gate shows the copy's steady -1.9% comes from fewer cached model pages for decode miss reads, measure whether S1/S2 change it. Otherwise record it as open.

### D5. Measurement

Each step is A/B against the previous kept state with the harness, `cold,append,decode` plus guards, `--bitwise`, without the copy. One run with the copy as a check. Report the detail metric "first token after the sweep" next to ttft and decode. The final A/B runs against the segment start, followed by parity.

## Risks / Trade-offs

- [Re-warming competes with the sweep's last reads] -> start after the last layer's experts are delivered; bounded by `mincore`.
- [Locking more memory starves the expert cache or the system] -> S2 only with the owner's review; the cache budget is unchanged unless approved.
- [macOS page-cache policy differs between runs] -> repeated runs, interleaved order, and `vm_stat` and `mincore` evidence rather than timing alone.
