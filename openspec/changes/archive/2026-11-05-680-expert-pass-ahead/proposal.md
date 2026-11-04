# Proposal

## Why

In streaming decode every layer still stops after its router: the GPU idles while the CPU sees the six selected ids, checks the expert cache and commits the routed expert pass, then pays about 100 us of restart. About 90% of layers have all six experts cached (`132` probe: 8739 of 9728 layer steps), and on those the CPU decides nothing the GPU cannot decide itself: the layer's address table already holds a GPU address for every cached expert and 0 for the rest, and the masked expert kernels already skip a zero address. The `132` probe measured 121.6 us of GPU idle before the expert pass on an all-hit layer; `210`'s mailbox has since taken about 25 us of wake off it. About 36 such stops a token come to roughly 3.5 ms, the same order as all of decode's SSD reads (about 4 ms, `40` S0) and about 10% of a decode 2048 token (28.7 t/s, 34.8 ms, Segment 1's latest row). It is the largest structural idle left in decode.

## What Changes

- On a single streaming box, commit the routed expert pass right behind the router, in the batch that already carries the shared expert (`132`'s split), before the ids are known: the masked gate/up SwiGLU and the six-expert down, all six slots active, ids read from the router's GPU buffer and addresses from the layer's address table. An expert that is not cached has address 0 and the kernels skip it.
- The CPU keeps reading the ids from `210`'s mailbox and does the same cache bookkeeping in the same order. On an all-hit layer it then commits the rest of the layer and the next layer's attention while the GPU still runs the expert pass, so the next batch is queued before the GPU goes idle and starts about 1 us after it (`130` D3), instead of about 100 us after a commit to an idle GPU.
- On a layer with a miss, the miss loads as today. Once the pre-committed pass has completed, the CPU publishes the loaded expert's address and commits the missing gate/up and the down over all six, as `145`'s split already does; the final down overwrites the pre-committed partial one. Nothing is rolled back: no later layer was committed.
- A rollback switch, `DS4_METAL_DISABLE_V41_EXPERT_PASS_AHEAD`, classified in `ds4_env.def`, listed in `AGENTS.md`, checked bitwise by `make test-deepseek41-decode-switch`.
- An S0 gate before any code: the all-hit idle on today's `main` (the ceiling), the CPU's reaction time against the GPU work queued behind the router (whether one layer of lead hides it), and whether the pass can run from GPU-side state alone with the same kernels and arguments as today (bitwise by construction) and an exact address table. The change closes at a failed gate.
- Not the rejected `132` D3 (an expert pass gated on a CPU-signalled event: a signal restarts the GPU no faster than a commit) nor `132` D4 (optimistic continuation with snapshots and a restart of the token): here the expert pass is not gated at all, and the gate moves to the next layer's batch, which the CPU commits while the GPU is still busy.

## Capabilities

### New Capabilities
None. Same results, different submission (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c`: `ds41_moe_partial` encodes the routed pass into the shared-expert batch on a single streaming box and skips it at the readback when it is already queued.
- `ds4_metal.m`: the streaming split path of `ds4_gpu_routed_moe_one_tensor` gains an ids-ahead encode (masked pair and masked sum6 with the full mask, no host ids), the readback (`ds4_gpu_split_readback` and the mailbox wait) learns that the pass is queued, and the miss path publishes new addresses only after the pre-committed batch completes. `ds4_gpu.h`: declarations.
- `ds4_env.def`, `AGENTS.md` (decode switch list), `speed-bench/perf-record.md` (gate figures, the A/B row, a rejected-ideas row if dropped).
- No upstream PR is ported; `docs/upstream-prs.md` is unchanged. Upstream's opt-in full expert address table is related and not taken (design D6).
- No external SSD. Output bitwise; cache policy and hit rates unchanged.
