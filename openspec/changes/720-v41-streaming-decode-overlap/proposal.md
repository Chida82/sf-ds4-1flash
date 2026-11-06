# Proposal

## Why

Five merged upstream commits are recorded as `history: resident`: upstream
runs them only when `!g->streaming`, with no reason given. A read of each
against this child's streaming decode:

- `be2773b` (pipelined single-host decode command buffers): already covered.
  Upstream itself lifted the streaming guard later (`4c29e82`, `8c54d7f`), and
  this child queues every streaming layer since change `30`.
- `57df7a5` (the same for the batched decode step): unreachable. Its guard
  reason is stated (the expert cache is reconfigured per layer), and this
  child refuses multi-session batches under streaming anyway
  (`ds41_sessions_batch_supported` returns false on `streaming`).
- `565db43` (finer pruning of the short-sweep decoder suffix): it saves rows,
  not expert reads, and the sweep waits on SSD reads, not compute. The
  rejected-ideas rows of `80` and `530` measured exactly that. Its exactness
  under the streaming kernels' row thresholds is also unproven.
- `f0b4f55` (one RoPE table per decode token): reachable in principle. The arm
  and take of its shared table happen inside one attention call, with no
  expert read in between. It saves about 8 dispatches and some cos/sin work
  per token. It fuses the index-query RoPE with the FP4 quantize, which since
  `97e3276` can round an exact FP4 midpoint differently from the separate
  steps, so it may not be bitwise here.
- `26335c7` (hyper-connection weights overlapped with the projections): the
  attention half has no expert read and is valid as is. The FFN half sits
  upstream beside a concurrent gate/up level that requires `!g->streaming`;
  here it would move into the window where the GPU already waits on the
  router readback (changes `132`/`210`).

Two candidates are left, both without an upstream figure and both probably
small. This change screens them cheaply before any port.

## What Changes

- Stage 0, a pre-screen: a scratch micro-bench of each candidate's kernels
  on this machine (the child's `DS4_METAL_*_SOURCE` swap), and the FP4
  midpoint check for `f0b4f55`. A candidate goes on only if its saving is
  large enough to show in the harness.
- For a candidate that passes: port it under streaming with a switch
  restoring the current path (upstream's names: the deferred HC switch for
  `26335c7`), bitwise, then one A/B.
- Record `be2773b`, `57df7a5` and `565db43` as dropped, with the reasons
  above.
- No output change; a candidate that is not bitwise is dropped.

## Capabilities

### New Capabilities
- `decode-overlap`: V4.1 decode work moved off the streaming critical path
  (shared RoPE table, hyper-connection weights overlapped with the
  projections), its exactness, and its switches.

### Modified Capabilities
- None.

## Impact

- Code (only for a candidate that passes stage 0): `ds4.c` (`ds41_attention`,
  the HC mix sites), `ds4_metal.m`, `metal/dsv41.metal`, `metal/dsv4_hc.metal`,
  `ds4_env.def`.
- Tests: kernel checks from the commits, `make test-deepseek41-decode-switch`
  per switch.
- Docs: `docs/upstream-prs.md` (the five-commit row split per commit),
  `speed-bench/perf-record.md` (pre-screen figures; a rejected-ideas row for
  each candidate that stops).
