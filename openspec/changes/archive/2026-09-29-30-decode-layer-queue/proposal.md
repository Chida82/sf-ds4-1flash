# Proposal

## Why

On one box, `ds41_graph_step` (`ds4.c` ~24502) ends and waits on the command
buffer after every one of the 40 layers. Only the TP pair queues layers.
Under SSD streaming, the routed MoE also ends a buffer inside each layer to
read back the six selected expert ids (the `use_iq2_selected_slots` path,
`ds4_metal.m` ~33026). That makes about 81 commit+wait round trips per token,
serialized with the SSD reads. [code]

#1041 `bd6f912` queues the layers on one box, and commits each layer without
waiting, so the GPU runs layer L while the CPU encodes L+1. It is the only
decode PR measured in our regime:

- M2 Ultra, V4.1 Q2, SSD streaming: 10.64 -> 12.08 t/s (+13.5%);
- 68,389,120 logit floats identical over 512 steps;
- the forced-eviction test passes.

[upstream, re-measured by the #1034 author]

The same function runs the token-major prefill tails (every tail under 1024
tokens after a sweep, i.e. about half the owner's 1-10K prompts). So the
gain shows in TTFT as well as in decode.

## What Changes

- **S0, tool.** From #1034 `9b50495`, port only the test and the bench flag.
  The queue code is superseded by #1041.
  - The forced-eviction check in `tests/test_deepseek41_graph.c`: two
    sessions share a 512-expert cache, and logits, Engram history and state
    spans are compared bitwise at positions 121-144. It is retargeted to
    #1041's switches.
  - `--ssd-streaming`, plus a cache-size pass-through, for
    `speed-bench/metal_decode_schedule_bench.c`.
- **S1.** Port #1041 `bd6f912` with two fixes the review found:
  - keep the queue off while `layer_resident` (quality + streaming).
    Otherwise `ds4_gpu_begin_commands()` returns 0 at layer 1 on the open
    batch, and `--quality --ssd-streaming` decode fails;
  - flush without waiting only when `tp_world == 1`. TP keeps its poll-gate
    packaging, which cannot be measured on this machine.

  The PR's rollback switches keep upstream's names
  (`DS4_METAL_DISABLE_V41_DECODE_QUEUE`, `DS4_METAL_DISABLE_V41_DECODE_FLUSH`),
  so an upstream merge lands as a clean sync.
- **S2, a variant measured against S1.** #1073 `2a281b08` + `29ce2717`:
  - a flush every second layer instead of every layer;
  - a separate buffer for the second Engram table, which removes the layer-13
    drain.

  S2 is kept only if it beats S1 by the keep rule; one mechanism stays.
- **Not taken.**
  - #1041 `fdbf7f2`: `history`, resident only (`whole_token` needs
    `!g->streaming`).
  - #1067: `not reachable`. Its queue needs `!streaming` and a pre-M5 chip,
    and its Engram threads are already in main (16 `dispatch_apply_f`
    readers).
  - #1049: `drop`.
- **Expected** [inferred]: decode +4-8% (about 8-11 ms per token), and the
  same on token-major tails. The per-layer id readback, the miss reads and
  the drains at layers 13 and 39 stay.

## Capabilities

### New Capabilities
None. Output is bitwise identical (`skip_specs: true`).

### Modified Capabilities
None.

## Impact

- `ds4.c` `ds41_graph_step` (about +20 lines), and the V4.1 Engram input
  buffer (S2).
- `tests/test_deepseek41_graph.c`, `speed-bench/metal_decode_schedule_bench.c`.
- Gate:
  - token-identical and bitwise logits against the previous step
    (`ab_bench.py --bitwise`);
  - the forced-eviction test;
  - `--quality --ssd-streaming` decodes;
  - expert-cache hit and miss counts equal between A and B;
  - parity.
- Registry lines: #1041, #1034, #1073 `2a281b08` `29ce2717`, #1067, #1049.
