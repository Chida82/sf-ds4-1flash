# M5 Max: hardware facts for inference decisions

Research snapshot: 2026-09-30. Target: this MacBook Pro and its internal SSD,
plus an ACASIS TB501 Pro enclosure containing a Samsung 9100 PRO 1 TB.

This is a hardware reference, not an implementation plan or a sync ledger.
It records the facts that inform performance work on DeepSeek V4.1 Flash.
New performance claims still need measurements on the final code under test.

## Evidence and units

- **Local observation:** read-only `system_profiler`, `sysctl`, `sw_vers` and
  SDK inspection performed during this exploration.
- **Official:** Apple documentation and vendor specifications linked below.
- **Reported measurement:** the owner's measurements and the existing
  `docs/ssd.md` report. No disk or model benchmark was rerun to write
  this document. Benchmark-method limitations are stated below.
- **Derived:** arithmetic using those observations, not a measured speedup.

GB and GB/s are decimal (10^9 bytes). GiB and MiB are binary (2^30 and 2^20
bytes). Apple labels this machine's memory as 128 GB; `hw.memsize` reports
137438953472 bytes, or 128 GiB. The child's cache argument ending in `GB` is
parsed as GiB by `ds4_parse_gib_arg`; do not mix it with decimal disk bandwidth.

## 1. Verified machine

| Property | Observation / evidence |
|---|---|
| Model | MacBook Pro, identifier `Mac17,6` (local) |
| SoC | Apple M5 Max (local) |
| CPU | 18 cores: 6 Super and 12 Performance (local) |
| GPU | 40 cores, Metal 4 support (local) |
| Physical RAM | 128 GiB (local) |
| Unified-memory bandwidth | Up to 614 GB/s for the 40-core configuration (Apple [1]) |
| GPU matrix acceleration | A Neural Accelerator in each GPU core (Apple [2]) |
| Separate Neural Engine | 16 cores (Apple [1]); not the GPU Neural Accelerators |
| OS | macOS 27.0, build `26A428` (local snapshot) |
| Selected tools | `/Library/Developer/CommandLineTools`, SDK 27.0 (local) |
| CPU matrix features | `FEAT_SME`, `FEAT_SME2`, `FEAT_SME2p1` report 1 (local) |
| VM page size | 16384 bytes (local) |
| CPU cache line | 128 bytes (local; not proof of every GPU transaction granularity) |
| Super-level L1D / L2 | `hw.perflevel0`: 128 KiB / 16 MiB (local) |
| Performance-level L1D / L2 | `hw.perflevel1`: 64 KiB / 8 MiB (local) |
| GPU wired-limit override | `iogpu.wired_limit_mb = 0` (local); not an unlimited-memory setting |

The cache values are what the named sysctls expose, not a measured complete
cache topology. No reliable exact M5 Max SLC capacity or DRAM latency was
established here. Do not size a kernel around the 96-128 MB SLC or 6.4 ns DRAM
figures in the supplied background reports. Nor should an A19 microbenchmark
or an assumed GPU clock be presented as this Mac's measured TFLOPS.

## 2. Unified memory: benefits and limits

CPU, GPU and other engines share physical memory. There is no discrete VRAM
upload step for a GPU reading a CPU-filled shared Metal buffer. However:

- 614 GB/s is an advertised aggregate ceiling, not a measured rate for every
  kernel, and not a separate allowance for the CPU and GPU each.
- Shared physical memory does not remove synchronization, cache misses,
  allocation/residency management, or contention between simultaneous work.
- SSD data still has to enter RAM. Neither UMA nor Metal I/O turns an SSD into
  GPU memory with DRAM latency or bandwidth.
- `MTLStorageModeShared` suits CPU-filled expert buffers. GPU-only scratch may
  benefit from `Private`; the runtime already selects it for some M5 scratch.
  Private buffers are not additional physical memory.
- Residency sets group allocations for GPU use. They do not create RAM or
  prove that every byte of an oversized mmap is physically resident.
- Leaving room for the OS and file cache matters. Increasing a wired limit can
  reduce useful file-cache capacity or cause memory pressure rather than speed
  inference up. No system memory settings were changed in this exploration.

Memory limits measured on 2026-10-09 (`225-mac-memory-evidence`):

| Limit | Value |
|---|---|
| `hw.memsize` | 137438953472 (128 GiB) |
| `iogpu.wired_limit_mb` | 0 (the system default) |
| `vm.global_user_wire_limit`, `vm.user_wire_limit` | 116823110451 (108.8 GiB) |
| Metal `recommendedMaxWorkingSetSize` | 107.52 GiB (84% of RAM) |

The engine's cache cap follows from the recommended size, not from RAM: the
model target is `min(86% x recommended, floor_GiB(7/8 x recommended -
context buffers))`, 86 GiB at ctx 32768, and both the automatic budget and an
explicit `NGB` cache flag stay under it. During a harness-shaped run the box
has about 1 GiB free and 23-25 GiB of file cache; see
`speed-bench/perf-record.md`, Memory levers, for the timeline.

Keep three different caches separate in reasoning:

1. the application's explicit expert cache in RAM;
2. macOS's file/page cache, which may satisfy expert `pread` calls;
3. the SSD's pseudo-SLC write cache, whose exhaustion affects long writes.

A miss in (1) does not necessarily imply a physical SSD read. A write cliff in
(3) is not a read-bandwidth cliff for previously stored model weights.

## 3. Native compute and execution APIs

### GPU Neural Accelerators: MPP / TensorOps

Apple's low-level route is `mpp::tensor_ops`, including `matmul2d` and
cooperative tensors [2, 3]. Merely using the older `simdgroup_matrix` API is
not equivalent to adopting the new accelerated TensorOps path.

Relevant documented capabilities:

- tensor BF16 support from macOS 26.1;
- cooperative tensors as matmul inputs from 26.3, enabling custom
  dequantization without a threadgroup-memory round trip;
- additional integer tensor formats in 26.4;
- FP8/FP4/INT2 formats and auxiliary scale planes in the 27.0 SDK, also found
  in this machine's installed `MTLTensor.h`;
- cooperative intermediate results, custom epilogues and locality-aware tile
  traversal; Apple specifically discusses Morton order and synchronization
  along the reduction dimension.

API availability does not establish a native hardware execution rate, GGUF
format compatibility, or bitwise equivalence. IQ2_XXS and Q2_K are not ordinary
INT2 tensors. Their codebooks/scales/layouts need custom decoding. Replacing a
reduction tree, intermediate precision or quantization format can change the
model's output even when the mathematical formula looks identical.

The child already detects M5 TensorOps support in
`ds4_gpu_detect_metal4_features` and uses packed MPP routed-prefill kernels,
including `kernel_mul_mm_id_mpp_packed`. This is not an unused accelerator
waiting for a global enable switch.

M5 also has second-generation Dynamic Caching. Occupancy, register pressure,
threadgroup storage and data locality remain relevant: larger tiles or more
fusion are not automatically faster. Automatic texture compression described
by Apple [4] applies to suitable texture resources, not arbitrary MTLBuffer
weights. Ray-tracing and media engines have no established role in this
inference path.

### Metal 4 submission is a separate question

TensorOps adoption does not require migrating the entire host runtime to
`MTL4CommandQueue`. The inspected runtime uses a traditional command queue
while using TensorOps in shaders.

Metal 4 adds command allocators, reusable command-buffer objects and argument
tables [5]. Reusing a command-buffer object does not mean automatically
replaying an unchanged inference graph. Resource lifetime and hazards become
explicit responsibilities; Metal 4 considers resources untracked. Indirect
compute commands and event synchronization can support more GPU-driven work,
but do not make disk misses or CPU dependencies disappear.

### CPU SME / SME2 and the separate ANE

SME/SME2 are present on this CPU. Apple documents operating-system support and
ABI considerations in XNU [6]. Feature presence alone does not establish the
number of independent matrix units, CPU memory throughput, or a profitable
CPU/GPU split for this model.

BNNS/BNNS Graph are CPU acceleration APIs, as Apple explicitly states [7].
They are not direct ANE APIs. Core ML and newer model frameworks provide
model-level hardware placement, not a drop-in way to execute this GGUF's
custom Metal kernels on the ANE.

GPU Neural Accelerators, CPU matrix extensions and the separate Neural Engine
must not be counted as interchangeable units. Splitting dependent operations
between them can add synchronization and memory contention. CPU crypto
instructions likewise do not accelerate tensor computation; Engram's learned
hash addressing cannot be replaced by a different hash algorithm.

## 4. Storage configuration and measured behavior

The owner supplied the headline measurements below. The existing
[`docs/ssd.md`](ssd.md) adds configuration, simultaneous-read
results and confirmation runs.

| Component | Internal | External |
|---|---|---|
| Device | Apple SSD AP2048Z, 2 TB, per local report | Samsung 9100 PRO 1 TB |
| Connection | Internal Apple storage | ACASIS TB501 Pro, TB5 / USB4 v2 at 80 Gbit/s |
| SSD-side link | Not established here | PCIe 4.0 x4 at 16 GT/s, per local report |
| Filesystem during reported tests | APFS | ExFAT, 128 KiB clusters, to 2026-10-07; APFS from 2026-10-08 (`250`, `speed-bench/perf-record.md`, External drive on APFS) |

The 9100 PRO is a PCIe 5.0 x4 SSD, rated at up to 14.7/13.3 GB/s read/write
for the 1 TB model on a suitable native interface [9]. That is not its rate
through this enclosure. TB5's display-oriented 120 Gbit/s boost is not an SSD
transfer budget; this Gen4 x4 storage path operates in the 6-7 GB/s class [10].
The measured 6.38-6.39 GB/s plateau is consistent with the bridge/link limit.

### Sequential transfers

| Test | Internal | External |
|---|---:|---:|
| Read ceiling, 8 MiB, 4-8 threads | 13.4 GB/s | 6.38 GB/s |
| Read 1 MiB, 1 thread | 10.8 GB/s | 5.2 GB/s |
| Read 64 KiB, 1 thread | 2.42 GB/s | 1.57 GB/s |
| Write before external pSLC exhaustion | 11.0 GB/s reported | about 5.2 GB/s |
| Write after about 45-50 GiB on external | Not measured | about 0.9-1.3 GB/s |

The local report's internal write run was 32 GiB; it does not establish its
longer sustained-write behavior. External confirmation runs reached cliffs
at 44 and 51 GiB. The cliff is consistent with pSLC exhaustion; the effects
of cache recovery, free space, TRIM and temperature were not isolated.
Copy/setup time must not assume the initial 5.2 GB/s continues over a GGUF.

### Small random reads

| Test | Internal | External |
|---|---:|---:|
| 4 KiB, one outstanding request | p50 67 us; 14.7k IOPS | p50 84 us; 11.1k IOPS |
| 4 KiB, 32 threads | 249k IOPS | 196k IOPS |
| 264-byte row, 16 threads | 173k IOPS | 139k IOPS |
| Batch of 24 rows, 16 threads | 0.27 ms | 0.27 ms |
| Batch of 48 rows, 16 threads | 0.40 ms | 0.40 ms |

Median latency and total IOPS are different statistics; one need not be the
exact reciprocal of the other. The equal short-batch times are not proof
that the devices have equal physical latency or equal Engram runtime cost.

### Large random reads and miss-shaped batches

| Test | Internal | External |
|---|---:|---:|
| 1 MiB, 18 threads | 13.7 GB/s | 6.39 GB/s |
| 48 x 816 KiB, 18 threads, roughly four expert misses | 3.27 ms | 6.40 ms |
| 1200 x 816 KiB, 18 threads, roughly 100 experts | 78.5 ms | 157 ms |

### Concurrent reads, from the existing local report

| Work on both devices simultaneously | Internal | External | Aggregate |
|---|---:|---:|---:|
| 1200 x 816 KiB, 18 threads per device | 13.0 GB/s | 6.38 GB/s | 19.4 GB/s |
| Random 1 MiB, 18 threads per device | 13.9 GB/s | 6.39 GB/s | 20.3 GB/s |
| Random 4 KiB, 32 threads per device | Per-device attribution not recorded | | 314k IOPS |

These results support concurrent bulk-read capacity, not guaranteed additive
performance during inference. CPU overhead, shared RAM, GPU activity, device
queueing and tail latency still need model-backed evaluation.

### Method limitations that affect decisions

The read-only inspection of [`speed-bench/iobench.c`](../speed-bench/iobench.c)
found these distinctions from the production engine:

- Read descriptors request `F_NOCACHE` and disable readahead, but the benchmark
  does not check those `fcntl` results. `F_NOCACHE` is not a page-cache purge;
  the report itself discarded a cache-contaminated 61 GB/s result after `dd`.
- The original disks were tested with different model files/spans. A later
  external confirmation used a newly written 64 GiB file. Small-read results
  differed; bulk bandwidth reproduced closely. Neither run isolates all
  filesystem, free-space or SSD-internal cache effects.
- `batch` creates/joins pthreads and allocates/frees buffers inside every timed
  repetition. Production decode uses a persistent expert pool, while Engram
  uses GCD. Short-batch equality may conceal device differences behind host
  overhead.
- `batch_worker` aligns every offset to 16 KiB, even for 264-byte reads. The
  sustained `rand` mode accepts row alignment, but the batch is not an exact
  Engram row-address replay, nor does it perform decoding, sorting or dedup.
- The 816 KiB expert pieces are an approximation. Actual IQ2_XXS gate/up and
  Q2_K down slab lengths differ; production also preserves related offsets
  within each expert instead of choosing every piece independently.
- The inspected engine's decode expert reader uses the ordinary model fd and
  can benefit from the file cache. Engram opens an uncached fd; the explicit
  prefill buffers open a separate uncached fd when available. Do not treat all
  three as identical to the uncached storage microbenchmark.
- Write timing alone does not prove durability: `iobench` also does not check
  the result of `F_FULLFSYNC`.

ExFAT does not natively provide POSIX symlinks or journaling. An APFS-hosted
repository symlink may point to a regular file on ExFAT; that is different
from storing the Hugging Face symlink-based cache on ExFAT. Do not adopt the
local report's blanket symlink claim. No filesystem conversion, cache move,
firmware update or model replication is authorized by this reference.

## 5. Model facts that give the hardware numbers meaning

The local Q2 GGUF directory was read without mapping or executing the model.
Its shapes agree with `DS4_SHAPE_FLASH41` and the official configuration [8].

| Quantity | Observed / derived value |
|---|---:|
| Complete GGUF | 340.60 GiB |
| Engram tables | 188.83 GiB |
| Routed expert weights | 142.38 GiB |
| Other weights | about 9.38 GiB |
| Routed weights in one layer | 3.5596 GiB = 3.8221 GB |
| Two-layer prefill reserve | 7.1191 GiB |
| Selected routed weights per decode token | 2.2247 GiB, six experts in each of 40 layers |
| Three dense families: q_b, output_a, output_b | 4.6484 GiB combined |
| Engram row requests per text token | 48 x 264 bytes = 12672 logical bytes, before storage amplification |

The model has 20 causal encoder and 20 decoder layers, 384 routed experts per
layer and one shared expert. Its conditional memory is huge on disk but sparse
per token. Model size is therefore neither bytes read per token nor physical
SSD traffic per token.

At ctx 32768 the graph's compressed KV plus index-cache arrays occupy about
200 MiB. The much larger total context allocation includes scratch, prefill
and carry buffers. Engram's full prefetch output alone can occupy 768 MiB.
Aliasing and compact carry already exist; they are not new opportunities by
merely being named.

The fixed benchmark configuration admits about 74.88 GiB / 8078 expert slots,
roughly 52.6% of all routed weight bytes. It cannot hold all approximately
152 GiB of main weights on a 128 GiB machine, even without the Engram tables.

Historical readings in [`speed-bench/perf-record.md`](../speed-bench/perf-record.md)
after the SSD-read work show a warm decode token at about 45.6 ms, including
2.2 ms of expert `pread` and 1.6 ms of buffer preparation. Its 36.3 ms `sync`
term waits for GPU work up to selected-ID readback; it is not SSD read time
and not all removable synchronization overhead. These are historical probes,
not a post-60/post-70 baseline.

## 6. Consequences for evaluating optimizations

- Prefill can benefit from compute throughput and data reuse; single-token
  decode often needs efficient matvec bandwidth and lower submission latency.
  Measure this model's kernels rather than extrapolating a dense-GEMM demo.
- Dense projections deserve attention alongside routed experts. Reading only
  selected experts does not remove the large dense-weight traffic.
- Kernel locality, register/cooperative intermediates and lifetime-aware RAM
  use can exploit M5 without changing weights or numerical reductions.
- The external SSD is additional bulk-read capacity, not a faster replacement
  for the internal SSD. Its larger sequential advantage over older interfaces
  does not imply a large steady-decode gain here.
- For sufficiently large independent reads, the concurrent 13.0/6.38 GB/s
  rates imply approximately 67% of bytes from internal and 33% from external.
  Ideal aggregate bandwidth is 19.38 GB/s, or 1.49x the internal rate. This is
  a transfer model, not a measured LLM speedup. Equal 50/50 mandatory striping
  would instead be limited to about 12.76 GB/s by the slower device.
- With I/O acceleration `s` and exposed critical-path I/O fraction `f`, the
  optimistic end-to-end speedup is `1 / (1 - f + f/s)`. Already-overlapped
  reads do not count fully in `f`. With `s = 1.49`, `f = 0.05` gives only
  about +1.7%, while `f = 0.40` gives about +15.2%.
- A different inode holding identical bytes has a different file-cache
  identity. Replication can duplicate cached pages. Preserve the useful
  internal-cache path rather than blindly diverting warm reads to external.
- Engram/offload, weighted replication and sharding are design alternatives,
  not enabled features. Current Engram loading checks the main GGUF's inode;
  decode expert reads use one global model fd; wide mmap prefill cannot be
  accelerated just by warming a different file's pages.

The existing encoder timeline, GPU-busy counters, cache statistics and A/B
harness are starting points. Timing probes can change synchronization; keep
anatomy measurements separate from uninstrumented end-to-end verdicts.

## Sources

Supplied background documents: `apple_m5_max.docx` and `m5_google.txt`.
They are leads, not authoritative specifications. In particular, do not carry
forward their unsupported SLC/throughput figures, BNNS-to-ANE claim, generic
INT2-to-GGUF equivalence, or unconditional Shared/zero-copy recommendations.

1. [Apple: MacBook Pro M5 Pro / M5 Max specifications](https://support.apple.com/en-us/126319)
2. [Apple: Accelerate ML workloads with M5 and A19 GPUs](https://developer.apple.com/videos/play/tech-talks/111432/)
3. [Apple: Optimize custom ML operations with Metal tensors](https://developer.apple.com/videos/play/wwdc2026/330/)
4. [Apple: Boost graphics performance with M5 and A19 GPUs](https://developer.apple.com/videos/play/tech-talks/111431/)
5. [Apple: Understanding the Metal 4 core API](https://developer.apple.com/documentation/metal/understanding-the-metal-4-core-api)
6. [Apple XNU: SME support](https://github.com/apple-oss-distributions/xnu/blob/main/doc/arm/sme.md)
7. [Apple: Support real-time ML inference on the CPU](https://developer.apple.com/videos/play/wwdc2024/10211/)
8. [DeepSeek V4.1 Flash model and configuration](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
9. [Samsung: 9100 PRO 1 TB specifications](https://www.samsung.com/pl/memory-storage/nvme-ssd/9100-pro-1tb-nvme-pcie-gen-5-mz-vap1t0bw/)
10. [OWC: Gen5 SSDs through TB5 / USB4 v2 enclosures](https://www.owc.com/blog/can-usb4-v2-and-thunderbolt-5-enclosures-deliver-pcie-gen5-speeds)
11. [Apple: Load resources faster with Metal 3 / Metal I/O](https://developer.apple.com/videos/play/wwdc2022/10104/)
12. [Hugging Face: cache structure and symlink limitations](https://huggingface.co/docs/huggingface_hub/guides/manage-cache)

Local implementation anchors: `ds4_engram.c`, `ds41_graph_alloc`,
`ds41_graph_memory`, `ds41_prefill_expert_read`,
`ds4_gpu_stream_expert_pread_into`, `ds4_gpu_detect_metal4_features`,
`kernel_mul_mv_q8_0_f32_impl`, and `kernel_mul_mm_id_mpp_packed`.
