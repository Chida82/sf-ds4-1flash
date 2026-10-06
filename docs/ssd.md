# Internal SSD vs external Thunderbolt 5 SSD

Measured 2026-09-30 on the M5 Max, 128 GB, with `speed-bench/iobench.c`. The
question: what the external drive is good for in this child (Engram rows,
expert slabs, model storage), compared with the internal SSD.

| | Internal | External |
|---|---|---|
| Drive | Apple SSD AP2048Z, 2 TB | Samsung SSD 9100 PRO 1 TB in an ACASIS TB501Pro enclosure |
| Link | Apple Fabric | Thunderbolt 5 (80 Gb/s); the drive negotiates **PCIe 16 GT/s x4 (Gen4)** inside the enclosure |
| File system | APFS, 4 KiB blocks | ExFAT, 128 KiB clusters, 93% full (69 GiB free) |
| Random-read span | `DeepSeek-V4.1-Flash-Q2.gguf`, 341 GiB | `DeepSeek-V4-Pro-...-imatrix.gguf`, 433 GiB |

## Method

Every read is a `pread` on a descriptor with `F_NOCACHE` and `F_RDAHEAD` off,
the way `ds4_engram.c` and the Metal expert streamer open the GGUF, so the page
cache is not measured. Random offsets cover the whole file (4 KiB aligned,
16 KiB for batches, 264 B for Engram rows). Reads run on the existing GGUFs, read
only; the write test uses a 32 GiB scratch file, deleted afterwards. One disk at
a time, except the section on concurrent reads. `threads` = requests in flight.

```sh
cc -O2 -Wall -o /tmp/iobench speed-bench/iobench.c
/tmp/iobench write <file> 32                 # sequential write, 8 MiB blocks
/tmp/iobench seq   <gguf> <bs> <threads> 8   # sequential read
/tmp/iobench rand  <gguf> <bs> <threads> 5 [align]
/tmp/iobench batch <gguf> <bs> <n> <threads> <reps>
```

## Results

### Sequential (model copies, cold loads)

| Test | Internal | External | Ext / Int |
|---|---|---|---|
| Write 32 GiB, 8 MiB blocks | 11.0 GB/s (8 GB/s for the first 5 GiB) | 5.15 GB/s, flat over 32 GiB | 0.47 |
| Read 64 KiB, 1 thread | 2.42 GB/s | 1.57 GB/s | 0.65 |
| Read 256 KiB, 1 thread | 6.78 GB/s | 3.53 GB/s | 0.52 |
| Read 1 MiB, 1 thread | 10.8 GB/s | 5.17 GB/s | 0.48 |
| Read 4 MiB, 1 thread | 13.0 GB/s | 5.78 GB/s | 0.44 |
| Read 16 MiB, 1 thread | 11.8 GB/s | 6.10 GB/s | 0.52 |
| Read 8 MiB, 4-8 threads (ceiling) | 13.4 GB/s | 6.38 GB/s | 0.48 |

### Random, small blocks (Engram-like, latency bound)

| Block | Threads | Internal IOPS / p50 / p99 | External IOPS / p50 / p99 |
|---|---|---|---|
| 264 B (Engram row) | 1 | 13.3k / 74 / 95 us | 11.3k / 89 / 104 us |
| 264 B (Engram row) | 16 | 173k / 87 / 153 us | 139k / 102 / 239 us |
| 4 KiB | 1 | 14.7k / 67 / 81 us | 11.1k / 84 / 102 us |
| 4 KiB | 4 | 57.5k / 68 / 102 us | 47.3k / 82 / 113 us |
| 4 KiB | 16 | 194k / 80 / 125 us | 165k / 93 / 147 us |
| 4 KiB | 32 | 249k / 125 / 188 us | 196k / 159 / 219 us |
| 4 KiB | 64 | 262k / 240 / 339 us | 204k / 309 / 381 us |
| 16 KiB | 1 | 13.5k / 74 / 98 us | 11.9k / 83 / 100 us |
| 16 KiB | 16 | 174k (2.85 GB/s) | 139k (2.27 GB/s) |
| 16 KiB | 32 | 242k (3.97 GB/s) | 184k (3.01 GB/s) |
| 64 KiB | 1 | 0.67 GB/s, p50 97 us | 0.61 GB/s, p50 106 us |
| 64 KiB | 16 | 7.42 GB/s | 5.66 GB/s |

### Random, large blocks (expert slabs, bandwidth bound)

| Block | Threads | Internal | External |
|---|---|---|---|
| 256 KiB | 1 | 2.20 GB/s, p50 118 us | 1.98 GB/s, p50 131 us |
| 256 KiB | 16 | 12.8 GB/s | 6.38 GB/s |
| 1 MiB | 1 | 4.80 GB/s, p50 213 us | 4.04 GB/s, p50 258 us |
| 1 MiB | 4 | 12.8 GB/s | 6.39 GB/s |
| 1 MiB | 18 | 13.7 GB/s | 6.39 GB/s |
| 4 MiB | 1 | 9.18 GB/s, p50 448 us | 5.48 GB/s, p50 766 us |
| 4 MiB | 4 | 13.7 GB/s | 6.39 GB/s |

### Batches shaped like ds4 (issue *n* reads, wait for all)

Shapes from the code: an Engram layer reads 24 rows of 264 B on 16 readers
(`ds4_engram.c`), two Engram layers per token; an expert miss is 9.49 MiB in
three ~3.2 MiB slabs, each split in four 16 KiB-aligned pieces (816 KiB) on 18
threads (`ds4_metal.m`, `_PREAD_SPLIT=4`, `_PREAD_THREADS=18`).

| Batch | Internal median | External median | Ext / Int |
|---|---|---|---|
| 24 x 264 B, 16 thr (one Engram layer) | 0.27 ms | 0.27 ms | 1.0 |
| 48 x 264 B, 16 thr (both Engram layers) | 0.40 ms | 0.40 ms | 1.0 |
| 12 x 3.2 MiB, 1 thr (4 misses, no split) | 4.51 ms | 7.52 ms | 1.67 |
| 12 x 3.2 MiB, 12 thr | 3.07 ms (13.0 GB/s) | 6.37 ms (6.25 GB/s) | 2.07 |
| 48 x 816 KiB, 18 thr (4 misses, split 4 = default) | 3.27 ms (12.3 GB/s) | 6.40 ms (6.26 GB/s) | 1.96 |
| 1200 x 816 KiB, 18 thr (~100 experts, a sweep) | 78.5 ms (12.8 GB/s) | 157 ms (6.38 GB/s) | 2.00 |

### Both disks at once

| Test, run concurrently on both | Internal | External | Sum |
|---|---|---|---|
| 1200 x 816 KiB, 18 thr each | 13.0 GB/s | 6.38 GB/s | **19.4 GB/s** |
| random 1 MiB, 18 thr each | 13.9 GB/s | 6.39 GB/s | **20.3 GB/s** |
| random 4 KiB, 32 thr each | 132k and 182k IOPS (which is which is not recorded) | | 314k IOPS (vs 249k internal alone) |

Bandwidth adds up with no loss on either side. Small-block IOPS add up too, but
each disk drops below its solo figure: past ~250k IOPS the limit is host-side
(syscalls, threads), not either drive.

## Confirmation run (same day, 587 GiB free)

Identity read from `system_profiler SPNVMeDataType SPThunderboltDataType`:
`Samsung SSD 9100 PRO 1TB`, firmware `0B2QNXH7`, link `x4 @ 16.0 GT/s`, SMART
Verified, in an ACASIS `TB501Pro` (firmware 62.62) running as USB4 v2 at
80 Gb/s. The span for these reads is a 64 GiB file just written by
`iobench write`, not a GGUF.

| Test | First run (433 GiB GGUF) | Confirmation |
|---|---|---|
| `dd bs=1m`, 24 GiB, buffered with kernel readahead (independent method) | — | 6.35 GB/s |
| `dd bs=64m`, 24 GiB | — | 6.38 GB/s |
| seq 8 MiB, 4 thr | 6.38 GB/s | 6.38 GB/s |
| seq 1 MiB, 1 thr | 5.17 GB/s | 5.24 GB/s |
| rand 4 KiB, 1 thr | 11.1k IOPS, p50 84 us | 14.7k IOPS, p50 76 us |
| rand 4 KiB, 32 thr | 196k IOPS | 199k IOPS |
| rand 1 MiB, 18 thr | 6.39 GB/s | 6.38 GB/s |
| rand 264 B, 16 thr | 139k IOPS | 157k IOPS |
| 24 x 264 B, 16 thr | 0.27 ms | 0.25 ms |
| 48 x 816 KiB, 18 thr | 6.40 ms | 6.39 ms |
| 1200 x 816 KiB, 18 thr | 157 ms | 157 ms |

Bandwidth figures reproduce to within 1%. Small-block latency is 10-15% better
here, most likely because freshly written data still sits in the SLC cache and a
64 GiB span is easier on the drive's mapping table; the first run's figures on a
large, old GGUF are the realistic ones for model files. Do not run `iobench`
after a `dd` over the same file: `F_NOCACHE` reads still hit pages `dd` left
in the page cache (one such run reported 61 GB/s and was discarded).

Reference specs: the 9100 PRO 1 TB is rated 14.7 GB/s read and 13.3 GB/s write
on a native PCIe 5.0 x4 slot; ACASIS rates the TB501 Pro "up to 6000 MB/s",
and a review on an M4 Pro measured 6.65 GB/s read and 5.65 GB/s write. The PCIe
tunnel in Thunderbolt 5 / USB4 v2 is limited by spec to Gen4 x4 (64 Gb/s,
8 GB/s raw), which leaves 6-7 GB/s after overhead: 6.38 GB/s is 64% of the
80 Gb/s link and about 81% of the tunnel's raw rate. The drive is not the limit.

### Long writes: the SLC cache runs out

| Run | Rate until the cliff | Cliff at | After the cliff |
|---|---|---|---|
| 64 GiB, 15 min after the 32 GiB run and a large delete | 5.15-5.26 GB/s | GiB 51 | 0.85-1.33 GB/s |
| 64 GiB again, about 1 min later | 5.10-5.30 GB/s | GiB 44 | 1.26-1.34 GB/s |

The drop is a step, not a slope, which is the SLC cache signature rather than
thermal throttling. The 9100 PRO 1 TB is reported with about 114 GB of pSLC
(108 dynamic + 6 static) on an empty drive; only 44-51 GiB were available here.
Two plausible reasons, neither verified: the cache had not fully recovered
between runs, and space freed on ExFAT may not have been trimmed, so the drive
still counts it as used, which shrinks the dynamic cache. Practical figure:
**about 45-50 GiB at 5.2 GB/s, then about 1-1.3 GB/s**. Copying a 341 GiB GGUF
onto this drive in one go took 208 s with `cp` (1.76 GB/s, 2026-10-05), not 1 minute.

## What the numbers say

- **The external drive is capped at ~6.4 GB/s by its link**, not by the drive:
  a 9100 PRO is a Gen5 drive, but the enclosure runs it at PCIe Gen4 x4. Every
  bandwidth-bound figure (large blocks, >=4 in flight) sits at 6.38-6.39 GB/s,
  about **half** of the internal 13.4-13.7 GB/s. Writes: 5.15 GB/s sustained.
- **Small reads are close.** At 4-64 KiB and low queue depth the external drive
  is 10-25% slower in latency (84 vs 67 us for 4 KiB at QD1) and 15-25% lower in
  IOPS at QD16-64. An Engram-shaped batch (24 or 48 rows of 264 B on 16 threads)
  takes **the same 0.27 / 0.40 ms** on both: at that size the thread fan-out,
  not the device, is the cost.
- **Expert misses are 2x slower on the external drive.** The default split-4
  path turns a 4-miss batch into 3.3 ms internal vs 6.4 ms external, and a
  prefill sweep is bandwidth bound in the same ratio.
- **The two drives are independent.** Read concurrently, they deliver 19-20
  GB/s together.

## Usage strategies

Estimates below come from the batch figures plus `perf-record.md`; none of
them was measured end to end with the model.

1. **Keep the main GGUF (expert slabs) on the internal SSD.** Decode at 2K
   reads ~41 MiB of misses per token (`perf-record.md`, Read path): about 2 ms
   internal, about 4-6 ms external, so roughly 19 -> 18 t/s. The first token
   after a prefill sweep, which is bandwidth bound, would grow by about 2x its
   read share.
2. **Engram tables are the natural candidate for the external drive.** They are
   189 GiB of the 341 GiB, read as 264 B random rows where the two drives tie at
   decode (0.27 ms per layer) and differ by ~20% at prefill (139k vs 173k IOPS
   at QD16). Moving them would free 189 GiB of internal SSD for little cost.
   **Not possible today without code**: the tables live inside the same GGUF,
   and `ds4_engram_table_open` opens the model path. It needs either a split
   Engram file or an option giving the Engram path.
3. **Prefill reads from both drives: implemented** as
   `DS4_METAL_PREFILL_REPLICA=<copy of the GGUF>` (`140-dual-ssd-prefill`).
   Routed `up` (31% of a layer's expert bytes) comes from the copy, gate/down
   from the internal drive, at once. Measured against internal-only, bitwise
   identical output: ttft 2500 +6.8%, ttft 10000 +8.3%, append +1500 +24%,
   decode unchanged; the copy costs about 7 s of checking at every engine open
   (`speed-bench/perf-record.md`, Dual-drive prefill after 132). Decode misses
   read only the internal drive. `145` measured reading their up part from
   the copy: decode 8192 -1.7%. A single miss is latency-bound, and the
   copy's floor (about 0.6-0.7 ms for 2-3 MiB) is slower than the internal
   drive reading the whole expert.
4. **Model storage and transfers.** Good as an archive for GGUFs:
   copying 341 GiB from it to the internal SSD is bounded by the 6.4 GB/s read,
   about 1 minute of pure I/O (`cp` or `hf` will be slower). Symlinks work on
   macOS ExFAT, so the Hugging Face cache (`HF_HOME`) can live there, and
   `download.sh` symlinks in `gguf/` can point to it.
5. **ExFAT caveats.** No journal, and `F_FULLFSYNC` returned in 0.00 s: eject
   before unplugging, or a copy in flight can be lost. macOS writes `._*`
   AppleDouble files next to each file. Writes past ~45-50 GiB fall to
   about 1-1.3 GB/s (see Long writes); reads are unaffected.
6. **Running a model directly from the external drive** (all of it on the
   external drive) works, but every bandwidth-bound path runs at half speed:
   only an option when the internal SSD has no room.
