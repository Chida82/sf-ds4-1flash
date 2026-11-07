# Proposal

## Why

At `82GB` the engine leaves the 9.37 GiB of static weights pageable ("remain
pageable to preserve runtime headroom"). `750` prefaults them, so they are
resident when a prefill starts. Even so, a prefill slows down when free memory
is at the kernel's floor, which happens whenever the file cache is full of
other data. Measured on 2026-11-07 (perf-record, `750`, and the probe below):
- The first 2048-token prefill took 15.6-15.8 s with a full file cache,
  against 12.6 s with free memory. Every static weight was resident in both.
- In the slow runs, command buffers waited about 290 ms each between commit
  and completion beyond their GPU time: 7-8 s per prefill in all. The GPU
  time itself was the same, 4.6 s (`DS4_METAL_CB_TIMES`).
- The GPU must wire pageable pages before it can use them. With free memory
  at 1.2-1.6 GiB, the kernel first has to evict file pages.
- Allocating the explicit expert buffers is not the cause: it took 205-238 ms
  in both states.

A probe build locks the static weights at `82GB` despite the safe-budget
check (`PROBE760_FORCE_STATIC_LOCK`, scratch only):

| Run | without the lock | with the lock |
|---|---|---|
| 2048 prefill, full file cache | 15.63-15.70 s | 12.67-12.69 s |
| 2048 prefill, warm | 12.58-12.65 s | 12.57 s |
| README sweep back to back, first 2048 tokens | 169.5-175.6 t/s | 179.8-181.7 t/s |
| same sweep, later frontiers and steady decode | | within 1% |
| peak wired, 32K context | 102.9-103.2 GiB | 103.4-103.6 GiB |
| peak wired, 256K context, copy and `--boost` | | 105.66 GiB |

The limit is `vm.global_user_wire_limit`, 108.8 GiB. Peak wired barely moves
because the GPU already wires the pageable statics while it uses them, so
they were mostly counted before.

## What Changes

- Under SSD streaming, lock the static weights whenever the expert cache and
  the statics fit under a wired-memory ceiling derived from the user wire
  limit and the context buffers. Today's check uses 7/8 of the Metal
  working-set recommendation, which refuses at `82GB`.
- Keep `750`'s prefault as the fallback when the lock does not fit or fails
  part-way.
- `DS4_METAL_DISABLE_STREAMING_STATIC_LOCK` already turns the lock off.

## Capabilities

### New Capabilities
- `static-weight-lock`: when the static weights are locked under SSD
  streaming, and how that decision is checked against the wire limit.

### Modified Capabilities
None.

## Impact

- Code: `ds4.c` (the `fits` decision at engine open, next to
  `ds4_streaming_manual_cache_safe_bytes`).
- Memory: peak wired +0.4 GiB at 32K. The file cache loses 9.37 GiB that was
  pageable; `750`'s server test must still see the statics resident (they
  would be locked).
- Output: unchanged, bitwise.
- Risk: upstream's comment on the 7/8 margin says that close to the Metal
  working set, short token-major prefills spend their time in VM/driver
  synchronization. The `append` (+300 tokens, token by token) and a 256K
  session must show no loss.
