# Design

## Context

- The explicit prefill buffers (`100`) read each layer's routed experts on 8 reader threads through `ds41_prefill_expert_open_nocache_fd`: a second open of the model with `F_NOCACHE`, and `F_RDAHEAD 0` on the `140` copy.
- Each reader coalesces adjacent experts into runs and calls `ds41_prefill_expert_pread(fd, dst, offset, len)`, which loops `pread` in 16 MiB requests.
- `dst` is `slot->dst[family] + (offset - family_offset)`: the buffer mirrors the file. Tensor data starts on 16 KiB (`experts.txt`: gate, up and down offsets are all multiples of 16384), and the slot buffers are page-aligned. So a file offset on a page boundary has its destination on one too.
- An expert range is 3041280 or 3870720 bytes, so a run starts on a page only when it starts at expert 0.

## Goals / Non-Goals

**Goals:**
- no page-cache residue from uncached reads on APFS;
- the decode statics stay resident through a sweep, as they did with an ExFAT copy;
- output bitwise identical.

**Non-Goals:**
- decode misses, which read through the cached descriptor on purpose (`240`: the cache serves 20-28% of them);
- Engram reads;
- the replica check's speed;
- re-warming the statics after a sweep (`200` S1, dropped).

## Decisions

### D1. Split only the head

`head = (16 KiB - offset % 16 KiB) % 16 KiB`; when `head` is non-zero and shorter than the request, the first `pread` reads `head` bytes. Every later request starts on a page, and the 16 MiB step keeps it there. The tail is left alone: an aligned start with an unaligned end left nothing in the cache. A short read that ends mid-page makes the next iteration split again.

### D2. No switch

The bytes and their addresses do not change. The only cost is one more `pread` per run, about 4 us of a reader's time against a 2.9 MiB read. A switch would add a branch that measures nothing.

### D3. Evidence

1. `make test`: the explicit-read cases cover split reads, RAM-first copies and cancellation.
2. Residency runs of the decode shape with the residency probe tracking the statics and the model's routed up, alternating `main` and this change, without the copy. The expected result is statics at about 8.8 GiB, page-ins near the ExFAT-copy figure, and a first token after 8192 near 250 ms.
3. Harness `cold,append,decode`, `--bitwise`, 3600 s, A = `main`, B = this change, without the copy.
4. With the copy on APFS: the same harness with `--env DS4_METAL_PREFILL_REPLICA` on both sides.
5. The keep rule: no headline below -0.2% with its CI below zero, and a gain on first token 8192, ttft 10000 or append +1500 with its CI above zero.

## Risks / Trade-offs

- **More requests.** Each run costs one extra `pread` for its head page, and a 16 KiB uncached read is latency-bound (about 0.1 ms). The 8 readers keep the drive busy, so the harness's ttft rows will show whether it matters.
- **Partial pages go through the cache.** The probe found none left after the read, but the split head is a cached request on APFS. At 16 KiB per run it is 0.5% of the bytes.
- **Other file systems.** ExFAT did not leak. The change is the same read on any file system, so ExFAT pays only the extra request.

## Migration Plan

Branch `perf/268-aligned-uncached-reads` from `main`; worktree `../sf-ds4-1flash-268`. No commit or push without a request.
