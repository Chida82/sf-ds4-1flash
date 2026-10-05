# Design

## Context

See proposal.md and `docs/MacM5.md`. Recorded simultaneous bulk rates are 13.0 GB/s internal and 6.38 GB/s external. Routed up is 30.56% of expert bytes, so source-by-family approximates the ideal 67/33 split: 18.72 GB/s versus ideal 19.38. These are transfer estimates. Current reader workers loop gate/up/down serially; changing only up's fd would not establish useful dual-device overlap.

## Goals / Non-Goals

**Goals:** improve exposed prefill waits at fixed cache/buffer capacity, with an optional existing source and identical outputs.

**Non-Goals:** changing the default model location, copying weights automatically, making internal space savings, striped filesystems, external decode misses, a sidecar format, or dynamic IO scheduling.

## Decisions

### D1. Opt-in scope and admission

After `130` is resolved, read `DS4_METAL_PREFILL_REPLICA` once at engine open. Absent/empty preserves the existing path. A nonempty value is an explicit request: require single-box Metal SSD streaming, non-quality Q2 with IQ2_XXS gate/up and Q2_K down, and the kept explicit-buffer path; reject unsupported modes clearly before inference. Per-sweep flows still unsupported by that path retain the existing canonical source and report that fallback.

Accept an existing complete replica outside the repository. Open it read-only/CLOEXEC, require a regular file with the same GGUF directory/layout and expected range bounds, and reject the same inode as the canonical source. Topology is reported, not inferred from a path string. A one-device replica can be used for correctness tests but not claimed as two-device speed evidence.

### D2. Content identity without a new manifest system

At engine initialization, compare all routed-up tensor bytes against the canonical file using two bounded 1 MiB buffers. Use separately opened uncached/readahead-disabled validation fds when supported, checking results without changing decode's fd flags. Hold the admitted replica fd open for engine lifetime; validate file identity/stat stability before and after the scan. File name, matching header, length or a fresh mtime alone is insufficient.

Free verification buffers before normal memory admission. Log compared bytes and wall time separately from inference. Do not repeat the full scan per session or sweep. Files must remain immutable while open; detect observed size/timestamp changes before reuse and reject them. No persistent trusted-digest cache in this version. This favors correctness and a small implementation over launch speed; the startup cost is a required reported limitation.

### D3. Concurrent family delivery

Reuse `100`'s RAM-source hits first if that step was kept. For remaining ranges, route gate/down to internal and up to replica, at unchanged canonical offsets, into disjoint parts of the existing destination slot. Keep the original canonical model map as the cache/weight identity.

With the pread implementation, assign internal and external workers concurrent range lists; start both before joining either. Keep the existing bounded total reader budget initially and measure a small split sweep (not 18+18 by assumption). Up has a separate queue/list so a worker's serial gate/up/down loop cannot serialize the devices. If `100` retained Metal I/O, express the two sources through that existing route instead of maintaining duplicate schedulers.

Ready means every required RAM copy and both source groups have completed successfully. The slot is not bound early. Preserve the next-layer overlap and two-slot lifetime; unsupported wide/encoder-only flows are not silently rewritten to use a different schedule. If `100` rejected its wide step, this feature initially covers only existing supported shapes.

### D4. Failure and ownership

An invalid requested source aborts engine creation with a path/reason. An IO failure during a sweep joins/settles all readers and GPU consumers, invalidates the partial session and returns an error. Do not race a canonical fallback write against an outstanding external write, cancel an OS read by abandoning its buffer, or promise a fixed unplug timeout. The caller can restart without the option. Tests inject errors/delays rather than disconnect user hardware.

### D5. Gate and measurement

First measure layer-ready waits on the post-130 baseline with internal-only storage. If even eliminating the candidate IO cannot clear the project threshold, stop. The same run settles decode: the only figure (2.2 ms of `pread` in a 45.6 ms token, `docs/MacM5.md`) predates `60`/`70`, and at f = 5% an ideal second device gives at most +1.7%. Re-read it on the current tree; it closes the decode question either way without a dedicated run. Reproduce the concurrent bulk test only with approved inputs; do not use the two unrelated GGUFs from iobench as model replicas.

For same-build trials use `--b-env DS4_METAL_PREFILL_REPLICA=...`; such runs legitimately have no canonical record row. Final A/B against the segment start can use explicit shared `--env DS4_METAL_PREFILL_REPLICA=...` only after proving A does not consume it and B does, from source and activation logs; the environment is recorded in the summary. Otherwise retain labeled diagnostic evidence and resolve record formatting rather than silently compare identical modes. Do not patch baseline inference code to fake this condition.

Target normal `cold,append`, with timed decode, both long guards, byte-identical layer buffers/logits/state and unchanged slots. Record requested bytes per source, RAM-copy bytes, exposed wait, reader split, filesystem, devices and replica identity. Aggregate GB/s is explanatory, not the acceptance metric. Record engine-open validation time, fresh-process TTFT including it, and repeated-request break-even separately; no claim of faster one-shot CLI startup. A/B process churn/verification costs count against the harness wall budget, so use smaller kind groups rather than exceed 3600 seconds. If the current harness cannot budget a full quad with verification, stop and propose the minimal measurement adjustment instead of bypassing its refusal.

### D6. Alternatives not shipped here

A 43.51 GiB up-only derivative reduces disk space/setup writes but needs a new validated format. Full 67/33 chunk striping has only a small theoretical edge over the family split. 50/50 mandatory striping is limited to about 12.76 GB/s. Whole-layer alternation can create slow critical layers; decode routing is too sparse/warm for a bulk-rate claim. None is automatically added if the chosen split fails.

Considered and not pursued: reading the startup expert-cache preload (about 75 GiB) from both devices saves about 2 s once per process; a pre-processed weight format either reads more bytes (the bottleneck) or changes quantization and output, while expert reads are already contiguous multi-MiB ranges, so a lossless reorder gains nothing. Decode stays canonical-only pending the D5 figure.

## Risks / Trade-offs

- RAM reuse changes the actual byte ratio -> measure per-source residuals; do not promise 18.72 GB/s.
- External IO competes with GPU or Engram -> end-to-end guards; no silent cache-capacity change.
- Two drives' DMA shares unified-memory bandwidth with the GPU -> at about 16 GB/s internal plus the external rate it is a few percent of the memory bandwidth the decode kernels reach (the vocabulary head reads 605 GB/s), and prefill sweeps wait on the drive, not on memory. The one place it can show is a memory-bound GPU phase running under the bulk reads, such as the 4096-row tiles of a wide sweep: compare the sweep's GPU section time (`DS4_METAL_V41_STAGE_PROFILE`) with and without the second source before crediting the drive. Decode reads only cache misses (10-40 MB per token), so a second drive neither adds much there nor takes bandwidth from its kernels.
- Replica validation dominates startup -> expose it and restrict claims to measured lifetimes.
- Removable drive failure -> explicit error, joined ownership and safe session invalidation.

## Migration Plan

Feature is off by default in all frontends. Branch `perf/140-dual-ssd-prefill`, document the inline environment option and immutable-replica requirement, keep the canonical HF model untouched, and require case-specific approval before any large file creation. Removing the option restores internal-only operation. Run parity with the option enabled as well as the default, verifying that the orchestrator actually targets the candidate. No commit/push is implied.
