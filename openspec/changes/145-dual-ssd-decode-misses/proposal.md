# Proposal

## Why

After `140`, decode still reads every missing routed expert from the internal SSD only. On `67b75b8` this `pread` takes 2.6-2.8 ms of a 42 ms token (6.2-6.6%, `speed-bench/perf-record.md`, Dual-drive prefill after 132), and the GPU waits through nearly all of it. The external drive with the validated `140` copy is idle during decode. The typical answer is 200-2000 tokens, so decode is the longest phase of the typical mix.

## What Changes

- When a `140` replica is admitted, read part of each decode expert miss from it, concurrently with the internal reads, into the same cache slot. Output and the expert cache budget stay identical; placement alone also leaves hit rates unchanged.
- Compare placement strategies with the harness, each against the previous kept step:
  - **family split**: `up` from the replica, `gate`/`down` from the model. `up` is 30.6% of an expert's bytes, close to the ideal 1/3 for a drive at half the rate, and it is exactly the range `140` already validates;
  - **miss-count placement**: a lone miss is split by family, and two or more misses are placed whole on alternating drives;
  - **byte-proportional split**: any byte range from either drive. This one needs the whole expert tables validated (about 142 GiB, roughly three times `140`'s startup check), so it is tried only if the earlier steps leave measurable read time;
  - **split-deferred threshold**: today resident experts compute while three or more misses load. Shorter reads may move the best threshold, so retune it.
- **Route-prediction prefetch**: in the same command buffer as layer N, apply layer N+1's router to the current state, and return the predicted ids with the selected-id readback that already happens, so no extra sync is added. Read the predicted experts that are not cached while the GPU finishes layer N, at most 1-2 per layer with a confident score, into a few staging slots. A staged expert enters the cache only if it is then actually selected, and the predicted experts are protected from eviction for one layer. A probe measures first how many real misses the prediction catches and how many reads it wastes, at two leads (the state before layer N+1's attention, and one layer earlier). Two drives give about 19 GB/s, roughly 2 experts per layer within a token, against about 0.11 misses per layer today: bandwidth is available, foresight is what is missing. A learned predictor (for example on the ANE) is considered only if the free router reuse falls short; the ANE adds Core ML dispatch latency on each of the 40 layers.
- Quantify, then keep or reject, the idea of starting an expert's compute before all its bytes arrive (the first bytes from the internal drive, the last from the external one). In decode one expert's matvec takes microseconds against about 690 us of read, and each extra GPU restart costs about 100 us (`132`). The measurement decides; if it is dropped, it gets a Rejected-ideas row.
- No new file format and no automatic copy. Without an admitted replica, behaviour is exactly the current one.

## Capabilities

### New Capabilities
- `dual-ssd-decode-misses`: decode expert misses read from both drives when a validated replica is admitted, with identical output and safe failure.

### Modified Capabilities
- `dual-ssd-prefill`: its requirement that the replica never serve ordinary decode reads is relaxed for the validated ranges that this change uses. Lands after `140` is archived.

## Impact

- `ds4_metal.m`, the decode expert `pread` tasks: a per-task descriptor and placement; for prefetch, a predicted-id readback beside the selected ids and a few staging slots.
- `ds4.c`, `ds41_moe_partial`: the next layer's router applied to the current state, only in the prefetch step. `ds4.c` passes the admitted replica descriptor to Metal. If byte-proportional placement is kept, `140`'s validation widens.
- Graph and Metal streaming tests, `AGENTS.md` and `docs/ssd.md`, `speed-bench/perf-record.md`.
- Needs the external SSD with the `140` replica mounted for every measurement.
- Expected gain for the family split: about 0.2 ms per layer with a miss, so +1.5-2% decode and a shorter first token after a sweep. Prefetch can at most hide the whole miss read (6.2-6.6% of a token) if the prediction catches the misses. Both are estimates, not measurements, and they add up.
