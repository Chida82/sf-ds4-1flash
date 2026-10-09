# Design

## Context

- **Budget.** `ds4_engine_configure_streaming_cache_budget` (`ds4.c`) prints `effective = prefill headroom + dynamic cache`: the headroom is `streaming_prefill_bytes`, the dynamic cache is `budget` slots of 9.49 MiB. Nothing changes it after open.
- **Explicit buffers.** `ds41_prefill_expert_buffers_init` allocates 2 x (gate, up, down) tensors of one layer's routed experts, page-aligned and mlocked, if they fit `streaming_prefill_bytes`; `ds41_prefill_expert_buffers_free` releases them at the end of the sweep. On failure the sweep falls back to mmap page-ins ("explicit expert buffers unavailable; using mmap prefill").
- **Slab pool.** Cache slots live in slabs of up to 4096 MiB (`ds4_gpu_stream_expert_alloc_slab_buffer`, `DS4_METAL_STREAMING_EXPERT_SLAB_MB`), shared storage, registered in a residency set attached to the queue (`40`). Free slots sit on `g_stream_expert_cache_free_slots`; a slot is claimed from there before any eviction. Entries carry `inflight_seq` and a protected flag; `ds4_gpu_stream_expert_cache_entry_reusable` is the victim test.
- **Context buffers at ctx 32768** (from `ds41_graph_bytes`): KV, index caches and windows 210 MiB; per-token scratch 95 MiB; Engram prefetch 768 MiB; batch rows x 8192 5096 MiB; carry rows x 32768 1364 MiB; packed activation buffer 512 MiB; sort and views 25 MiB. Everything but the first two groups is used only by sweeps.
- **Memory during decode** (`210` A/B, mactop once a second): used 114 GB, available 23 GB (min 14.7), compressed 6.5 GB, swap 1.3 GB, pressure level 1.

## Goals / Non-Goals

**Goals:** more resident experts during decode without raising the box's peak footprint; prefill unchanged in result and, within the harness resolution, in time; output bitwise; a single switch back to the fixed budget.

**Non-Goals:** a different victim policy (`110` settled LRU vs decayed hotness; only the decay interval is swept here), changing the explicit buffer scheme or the reserve size, TP and resident paths, the `--ssd-streaming-cache-experts` semantics (the flag still names the dynamic cache; growth is on top of it and printed).

## Decisions

### D1. Gate: memory accounting before code

Measured by `225-mac-memory-evidence` (its timeline and miss curve); this change reads the tables. The timeline samples, once a second, `vm_stat` (compressor pages, pageins, pageouts, swapouts), `footprint` of the engine process (phys footprint, compressed, resident) and mactop's memory block, through: engine open, a 5000-token prefill, 256 decode tokens, a second prefill. Two facts come out:

- the real headroom during decode, which bounds S1 (if the prefill peak already swaps, S1 is cut below 770 slots or dropped);
- whether the prefill-only context buffers are resident during decode or compressed by the OS, which decides S2 (compressed pages cost nothing today, so releasing them gains no memory and only adds a reallocation at the next sweep).

### D2. Growth unit: lent slabs sized to the reserve

After `ds41_prefill_expert_buffers_free`, the pool allocates two slabs whose combined size equals the explicit buffers' total (3.56 GiB each, about 385 slots), tagged *lent*, registered in the residency set, their slots pushed on the free list. Decode claims free slots before evicting, so the new slots fill with misses and no entry is displaced.

Alternative, raising the budget and letting the victim scan absorb it: rejected. Lent entries would spread across every slab, and the reserve could not be given back without evicting arbitrary entries from slabs that stay allocated.

### D3. Shrink before the next sweep

Before `ds41_prefill_expert_buffers_init`, the engine drains pending command buffers (the prefill start already waits them), evicts every entry in the lent slabs (skipping none: after the drain nothing is in flight; protected entries are moved to the first free or victim slot elsewhere, copy of 9.49 MiB each, counted), removes the slabs from the residency set and releases them. The explicit buffers then allocate as today. If the release cannot complete, the sweep takes the existing mmap fallback: correct, slower, counted and printed in the streaming summary (`cache growth: +N slots, M shrinks, K fallbacks`).

Entries evicted at the shrink are lost regardless of hotness. Alternative, migrating the hottest lent entries into victims elsewhere before the release: a refinement if the first token after a sweep, or the append kinds, show the loss.

### D4. Hotness decay override

`DS4_METAL_STREAM_EXPERT_HOTNESS_DECAY_TOKENS` is an enum constant (16) read at the decay check; it gets an environment override, `DS4_METAL_STREAMING_EXPERT_HOTNESS_DECAY_TOKENS`, read per call so the harness `--b-env` can set it. Swept 8/16/32 in the same session; 16 stays unless a CI separates.

### D5. S2, prefill-only context buffers

`ds41_graph_alloc` is split: the static part (KV, index caches, windows, per-token scratch) stays for the session; the prefill part (`batch.*`, `carry.*`, `engram_prefetch`, the packed activation buffer, their views) is allocated at the start of a sweep and released at its end, with the growth of D2 extended by its bytes. Allocation and first touch of about 7.7 GiB per sweep are the cost; it shows in ttft and is measured against S1. Attempted only if D1 shows those pages resident during decode and S1 was kept.

### D6. Evidence

- `make test`; `test-metal-ssd-experts`, `--stream-decode-queue-parity`, `test-metal-command-memory`; a CLI run printing the growth line.
- Harness `decode,append` with `guard-16896,guard-decode`, `--bitwise --cache-policy-change`, against the previous kept tree: hit rates and miss counts per kind, first token after the sweep, ttft; mactop memory and `vm_stat` swapouts sampled during the run; the keep rule.
- One row per step (S1, decay, S2) in `perf-record.md`, with the memory figures.

## Risks / Trade-offs

- Memory pressure -> S1 never exceeds today's prefill peak; S2 is gated by D1; swapouts during an A/B invalidate the run.
- Churn at every request: up to 770 evictions and their later re-reads -> the append kinds and the cold guard bound it; short-answer workloads are where it can turn negative.
- Residency set add/remove per sweep -> measured once with `DS4_METAL_CB_TIMES`; the slab residency switch still turns the set off.
- Shrink while entries are in flight -> the drain precedes it; the mmap fallback covers a failed release.
- The `--ssd-streaming-cache-experts` figure no longer describes the whole cache -> the summary prints both the fixed budget and the growth.

## Migration Plan

Branch `perf/230-expert-cache-growth` from `main` once `220` has landed. The switch joins the decode list in `AGENTS.md`; the memory figures in "SSD streaming is not optional" are updated. No commit or push without a request.

## Open Questions

- Whether one lent slab or two releases faster: decided at 2.1 by timing the release and allocation of each shape.
