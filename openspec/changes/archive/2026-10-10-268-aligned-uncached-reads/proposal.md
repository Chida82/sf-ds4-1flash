# Proposal

## Why

`200` found that a long prefill sweep evicts up to 3.9 GiB of the decode statics, and that the first token after it pays 0.3-0.65 s to page them back. With the `140` copy on ExFAT they stayed resident, and why was not traced. `250` then measured the first token after 8192 at 875-920 ms with the copy on APFS against 180-200 ms on ExFAT, on the same tree.

The cause is the prefill reads themselves. The explicit prefill buffers read experts through a descriptor with `F_NOCACHE` and `F_RDAHEAD 0` (`ds41_prefill_expert_pread`), which should bypass the page cache. On APFS, a read that does not start on a 16 KiB page goes through the cache anyway (`nocacheprobe2`, scratchpad, 20 routed-up ranges, each evicted first):

| Read | Pages left in the cache |
|---|---|
| as the engine addresses it (expert ranges start every 3041280 bytes, 2 KiB-aligned) | 982 of 3731 (26%) |
| the same range, partial first page read on its own, the rest from a page boundary | 0 of 3731 |
| page-aligned start, unaligned end | 0 of 3717 |
| unaligned start, aligned end | 976 of 3713 |
| page-aligned start, destination off by 2 KiB | 2419 of 3699 |

The same holds on the APFS copy. In the residency runs of the 8192 decode shape, the statics fell from 8.79 to 5.7-7.0 GiB without the copy, with 1.3-1.9 M page-ins, and the first token took 0.93-2.4 s. With the copy on ExFAT, whose user-space file system does not leak, a third of the reads moved off APFS: statics stayed at 8.3-8.5 GiB, page-ins were 0.15-0.60 M, and the first token was 245 ms. With the copy on APFS, its pages appeared in the cache (16% of the sampled up ranges) and the first token was 477 ms.

## What Changes

- `ds41_prefill_expert_pread` reads the partial first page of a request on its own. The rest starts on a page boundary, and so does its destination: the explicit buffers mirror the file's layout from page-aligned memory, and tensor data starts on 16 KiB.
- That is every uncached read: the explicit prefill buffers, from the model and from the copy, and the `140` replica check.
- Output is bitwise identical: the same bytes land at the same addresses.
- No switch. A split read costs one more `pread` per range: about 1100 more per layer sweep, on 8 readers.

## Capabilities

### New Capabilities
None (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: `ds41_prefill_expert_pread`.
- `speed-bench/perf-record.md`: the probe, the residency runs, the harness rows; the `200` row in Rejected ideas gains a pointer.
- `AGENTS.md`, README: the first-token figure after a long sweep, if it moves.
- On ExFAT nothing should change: it did not leak.
