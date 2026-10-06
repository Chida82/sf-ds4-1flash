# Proposal

## Why

`180`'s diagnosis found what makes the first token slow after a long prefill sweep:
- the decode reads about 7 GiB of model pages back from the internal SSD;
- `vm_stat` counts 7.35 GiB of page-ins in the 3.5 s after a 6144-row sweep without the `140` copy, and 3.7 GiB with it;
- the first token after an 8192 context took 1.30-1.43 s without the copy and 0.18-0.34 s with it, while the GPU sat 19-50% idle.

The likely culprit is in the logs: with the measured cache (`--ssd-streaming-cache-experts 82GB`) the engine prints "static weights remain pageable to preserve runtime headroom", and the ~9.4 GiB of weights every token uses are left evictable. The fix would help every user, with or without a second drive. The first token after a sweep is also inside `ttft` whenever a prompt ends with a token-by-token tail (2500, 5000), so ttft can gain too.

## What Changes

- **Gate.** Confirm which pages come back and why:
  - sample `mincore` on the model mapping before the sweep, at its end and after the first token, mapped to tensor names;
  - measure the page-ins per harness shape;
  - find out what evicts them during the sweep;
  - check why the copy keeps half of them resident.

  Stop if the static weights are not the reloaded pages, or if the recoverable time cannot clear the harness resolution.
- **Candidate fixes, each measured as its own step:**
  - S1: re-warm the static spans in the background during the sweep's last layers (`madvise(WILLNEED)`, or a bounded page-touch on spare reader threads), so the first token finds them resident;
  - S2: keep the static spans resident through the sweep within the existing budget. For example, lock them when the explicit prefill buffers are not in use, or count them in admission so that the lock fits. This changes memory admission, so it needs the owner's review of the admitted figures;
  - S3, only if the gate shows it: the steady decode -1.9% with the copy, if it has the same cause (decode miss preads were 0.76 against 0.73 ms).
- Output stays bitwise identical; the expert cache budget is unchanged unless the owner approves S2's admission change.

## Capabilities

### New Capabilities
None (`skip_specs: true`): residency and timing only, with no externally visible behaviour.

### Modified Capabilities
None.

## Impact

- `ds4.c`: the static-weight lock decision near engine open, and the end of `ds41_graph_prefill_sweep`, if S1 or S2 is kept. Possibly `ds41_memory_admit`.
- `speed-bench/perf-record.md`, `AGENTS.md` (the streaming section), and the README's first-token figures if they change.
- Measured mainly without the external SSD, with the copy run as a check. The external SSD is needed only for that check.
