# Design

## Context

See proposal.md for the motivation.

A decode miss is loaded in `ds4_metal.m`. Each missing expert becomes `pread` tasks for its gate, up and down ranges. A task of at least 256 KiB is split into 4 pieces aligned to 16 KiB (`DS4_METAL_STREAMING_EXPERT_PREAD_SPLIT`, `40`), and the pieces run on an 18-thread pool, all on `g_model_fd`. When three or more of a layer's six experts miss, the split-deferred path computes the resident experts while the missing ones load; otherwise the GPU waits.

The internal-only gate run of `140` (decode 2048 and 8192, 256 tokens, `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`) measured:

| Figure | 2048 | 8192 |
|---|---|---|
| Layers with a miss | 1032 | 970 |
| `pread` per miss layer | 0.69 ms | 0.69 ms |
| Buffer prepare per miss layer | 0.39 ms | 0.37 ms |
| Split-deferred layers | 8 | 9 |
| Mean experts missing per layer | 0.11 | 0.11 |

So almost every miss layer misses a single 9.49 MiB expert, and the split-deferred path almost never runs.

`140` admits the replica at engine open. The admission:
- compares the header and every routed `up` tensor;
- keeps the replica open with `F_NOCACHE` and `F_RDAHEAD` off;
- records the replica's size and modification time and checks them before each prefill read.

## Goals / Non-Goals

**Goals:** shorten the exposed wait of decode misses with the second drive, at the same cache budget and with identical output; choose the placement by measurement.

**Non-Goals:**
- Changing the cache policy or its budget.
- Engram placement (`150`) and the KV cache (`160`).
- A new file format.
- Making the replica default-on without a configured path.

## Decisions

### D1. Gate (S0)

The gate runs on the tree after `140`, with the replica admitted and decode still reading only the model. It measures:
- per token: the exposed miss wait, and `pread` against buffer prepare;
- the miss-count distribution per layer;
- per drive: the latency of one expert's family pieces (gate/down about 6.6 MiB internal, up about 2.9 MiB external, each in 4 pieces) with the production pool;
- the GPU time of one routed-expert pass in decode (`DS4_METAL_ENCODER_TIMELINE`), which bounds D5.

If removing a third of the `pread` time cannot exceed the harness resolution on decode 2048/8192, stop and record the figure.

The 0.39 ms buffer prepare is not disk time. It is reported as a separate lead and not absorbed into this change.

### D2. Plumbing

`ds4.c` hands Metal the admitted replica descriptor and the validated ranges, through a setter beside `ds4_gpu_set_model_fd`. A `pread` task carries its descriptor, so placement is a property of the task and the pool is shared. Without a replica every task gets `g_model_fd`, which is today's behaviour.

### D3. S1 family split

The up task of a missing expert goes to the replica and gate/down stay on the model, with the same pieces, pool and destination. This is the only step that needs no wider validation.

Expected effect: an expert ready in about max(6.6 MiB / 13 GB/s, 2.9 MiB / 6.4 GB/s), about 0.47 ms, against 0.69 ms.

### D4. S2 split-deferred threshold

With shorter reads, re-measure the threshold of 3 (try 1, 2 and 3) on top of the kept S1. It is a constant today, and it stays one.

### D5. Compute before the expert is complete

Measured, not built first. The GPU does not see bytes written while a kernel runs (`132`), so starting early means extra command-buffer stages. Each stage costs about 100 us of restart (`132`), and in decode one expert's matvec takes microseconds.

If the D1 timeline confirms that the compute share is under the restart cost, the idea goes to Rejected ideas with both figures. Otherwise the smallest variant is tried as its own step: gate/up first, down after its bytes.

The same idea for prefill is out of scope: after `140` the prefill sweeps wait on the GPU, not the drive.

### D6. S3 wider validation, byte-proportional and miss-count placement

Both need gate/down bytes from the replica, so `140`'s check must cover every routed tensor: about 142 GiB, roughly three times its 6.7 s at engine open. This step is tried only if S1/S2 leave exposed `pread` time worth more than the threshold. It is measured as one step against the kept state, and its startup cost is reported with a break-even request count.

Within S3:
- byte-proportional placement gives the replica about 1/3 of each expert's bytes at any offset;
- miss-count placement splits a lone miss and places two or more misses whole on alternating drives.

The better of the two is kept, if either is.

### D7. S4 route-prediction prefetch

**Predictor.** Layer N+1's router (its gate weights, about 3 MB) applied to the current state, in the same command buffer as layer N. The predicted top ids are read back with layer N's selected ids, so no new sync point is added. Lead time is the rest of layer N plus layer N+1's attention, about 1 ms, which is enough for a 9.49 MiB read at the drives' rates. The rejected-ideas note under Expert cache after 100 already names route foresight as the only way to avoid the remaining misses.

**Probe (gate of S4).** A probe tree, never landed, logs per token and layer:
- the predicted top-k for the next layer, with scores;
- the selected ids;
- which selected ids were misses.

Leads tried: the state at the input of layer N+1's attention, and the state at layer N's input.

Report:
- recall on misses: the share of misses that the prediction would have read in time;
- wasted reads per token: predicted, not cached, not selected;
- how both change with a score threshold and a per-layer cap of 1-2.

Popularity from the cache's decayed hotness is tried as a filter: a predicted rare expert with a low score margin is skipped.

**Stop rule.** If no threshold catches enough misses to beat the harness resolution, net of the wasted reads' cost in bandwidth, S4 stops with a Rejected-ideas row and both figures.

**Mechanism, if the probe passes.**
- Prefetched experts land in a small set of staging slots outside the cache budget, bounded and counted.
- A staged expert is promoted into the cache only when it is actually selected; an unused one is dropped.
- Predicted experts are protected from eviction until the next layer is bound.
- Output stays bitwise identical. Cache statistics may differ from the no-prefetch run, and the A/B reports them; the cache budget does not change.

**Learned predictor.** It is only a follow-up if router reuse falls short, mainly to see further ahead (2-3 layers). The ANE is reachable only through Core ML: about 0.1-0.5 ms of dispatch on each of 40 layers, inference only. So a learned model would first run on the GPU in the same command buffer.

### D8. Measurement

Both arms run with the shared `--env DS4_METAL_PREFILL_REPLICA=<path>`, so prefill behaves the same and only decode differs. The harness emits a record row with a shared environment.

Target metrics: decode 2048 and decode 8192; also the first token after a sweep and guard decode 2500. The keep rule is the project's. The final evidence is an A/B against the segment start with the same shared environment (the start tree ignores the variable), plus parity with and without the replica.

## Risks / Trade-offs

- [Small reads on the external drive have higher latency (84 against 67 us at 4 KiB)] -> D1 measures the actual piece sizes. If up pieces finish later than gate/down, S1 is dropped or its split re-tuned.
- [Decode Engram reads share the internal drive] -> the internal reads shrink with S1, so contention can only fall. The guards check it.
- [The replica descriptor has `F_NOCACHE` while the model descriptor uses the page cache] -> the bytes are identical. A difference in speed is measured, not assumed.
- [Wider validation lengthens every engine open] -> only in S3, reported with a break-even count, and dropped if the gain does not pay for it under typical server use.
- [A pulled cable during decode] -> the step fails with an error and the slot stays invalid. The engine never falls back to rereading a partially written slot.

## Migration Plan

Branch `perf/145-dual-ssd-decode-misses` after `140` lands. There is no new option: decode uses the admitted replica only when `DS4_METAL_PREFILL_REPLICA` is set. If decode use is kept, the option keeps its name, and the docs say it serves both phases. Renaming it is a separate decision for the owner. Removing the variable restores internal-only reads.
