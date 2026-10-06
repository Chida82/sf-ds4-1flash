# Proposal

## Why

`140` speeds up V4.1 Flash prefill on a machine with a second SSD (ttft about 6-8% shorter, append +1500 about 20% shorter). The owner wants to know what the same idea is worth in the original ds4, and to have a branch ready for a possible upstream PR. Original ds4 does not have this child's explicit prefill buffers (`60`, `100`): its prefill warms the page cache with `pread` and the GPU reads the model's mmap. `140`'s mechanism therefore does not port as is.

## What Changes

- **Approach A only, for now.** In the owner's ds4 fork (`~/github/chida82/ds4`, a branch off `main` at `0aaea5a`), add the second-drive logic adapted to ds4's mmap path, for V4.1 Flash only:
  - an opt-in path to a byte-identical copy of the GGUF, validated at engine open on the routed up ranges;
  - the copy mmapped;
  - the GPU binding routed `up` from the copy's mapping and gate/down from the model's, during prefill page-in;
  - the page-in workers warming each family on its own drive.

  Output must stay bitwise identical.
- Measure original ds4 against ds4 with the port, with ds4's own bench, on V4.1 Flash Q2, under SSD streaming with the fixed cache, the same prompts and greedy output. Record the result here.
- **Nice to have, only after A's measured gains are known.** Each is decided separately with the owner:
  - porting the explicit prefill buffers (`60`, `100`) and then `140` as it is in this child;
  - other child improvements relevant to the second drive.
- No push, PR or upstream contact without the owner's explicit request.

## Capabilities

### New Capabilities
None in this child (`skip_specs: true`): the code lives in the ds4 fork, and this change holds the plan and the evidence.

### Modified Capabilities
None.

## Impact

- `~/github/chida82/ds4`: a feature branch, with `ds4.c` (and `ds4_metal.m` if the model-map binding needs it) for V4.1 Flash only.
- This child: `speed-bench/perf-record.md` (a cross-repo section) and `docs/upstream-prs.md` (an outgoing-port line).
- Needs the external SSD with the `140` copy.
