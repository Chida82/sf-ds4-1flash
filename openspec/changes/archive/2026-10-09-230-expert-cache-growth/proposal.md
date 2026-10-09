# Proposal

## Why

On a single streaming box the expert cache budget is fixed at engine open as the total minus the prefill reserve: 7.12 GiB for the two explicit layer buffers that a sweep allocates at its start (`ds41_prefill_expert_buffers_init`, mlocked) and frees at its end. Through every decode token that reserve is empty memory. The context buffers add to it: of the 8.07 GiB allocated at ctx 32768, about 7.7 GiB are prefill-only storage (batch rows x 8192, carry rows x 32768, the Engram prefetch, the packed activation buffer) that no decode kernel touches.

At the harness cache (82GB flag, 8078 slots) decode runs at a 0.90 hit rate and append at 0.95; the throughput is bounded by the miss reads. The Argodrive fork measured +2.96% steady decode (13.1 -> 11.1 misses per token) from a 9.5% larger cache at pp512/tg512 on a V4.1 Q4 box. The reserve alone is 770 slots, +9.5%.

Memory is not loose, though. During the `210` A/B decode runs mactop recorded 114 GB used of 137, 23 GB available (minimum 14.7), 6.5 GB compressed and 1.3 GB of swap at pressure level 1: the system already recycles part of the idle buffers by compression and uses the rest as page cache for the miss reads. The gain is real only to the extent that explicit slots beat that implicit reuse, and the change must never exceed the footprint the box already carries at the prefill peak.

## What Changes

- **Gate first, memory accounting.** During a decode and across a prefill: resident set, compressed pages, swap, free headroom (`vm_stat`, `footprint`, mactop). It fixes how much growth is admissible and whether the prefill-only context buffers are resident or already compressed.
- **S1, growth into the reserve.** After a sweep frees its explicit buffers, the cache adds two "lent" slabs sized like them and pushes their slots on the free list, so decode fills them before evicting. Before the next sweep allocates its buffers, the entries in the lent slabs are evicted and the slabs released. The footprint never exceeds today's prefill peak (cache plus reserve). Switch `DS4_METAL_DISABLE_V41_CACHE_GROWTH`.
- **Hotness decay sweep.** The victim policy's decay interval (`DS4_METAL_STREAM_EXPERT_HOTNESS_DECAY_TOKENS`, 16) gets an environment override and is swept at 8/16/32 in the same measurement session.
- **S2, prefill-only context buffers (conditional).** If S1 is kept and the gate shows those buffers resident during decode, they are released after a sweep and reallocated at the next one, and their bytes (about 830 slots) join the growth. The allocation cost returns as a ttft delta and is measured.
- Output is unchanged by construction: cache contents decide which experts are resident, never the arithmetic. The harness runs `--bitwise` and `--cache-policy-change`, since hit rates differ by design.
- Expected: low single digits on decode, most on long answers; a cost at every prefill (up to 770 evictions and the reads that follow) that the append and guard kinds must bound.

## Capabilities

### New Capabilities
None. Same results, different cache size over time (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4_metal.m`: slab pool growth and release (lent slabs, free-slot list, residency set), eviction of a whole slab honouring protected and in-flight entries, the decay override, the streaming summary line.
- `ds4.c`: hooks where the explicit buffers are freed and before they are allocated; for S2, `ds41_graph_alloc` split into static and prefill-only parts.
- `AGENTS.md` switch list and the memory figures in "SSD streaming is not optional"; `speed-bench/perf-record.md`.
- Works the same with one drive or with the `140` replica: decode misses always read the model file. TP, resident decode and prefill arithmetic untouched.
