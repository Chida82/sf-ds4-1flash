# Design

## Context

See proposal.md (Why). Facts from the code and the PR diffs that shape the
port:

- **Where V4.1 loads a missing expert.** Decode and token-major tails run
  `ds4_gpu_routed_moe_one_tensor` (`ds4_metal.m` ~33745): the selected ids are
  read back once per layer, then either `begin_selected_load` (the deferred
  split, three or more misses) or `load_selected_missing` reads the missing
  experts on the calling thread through the pread pool. The prefill sweep
  loads through `prepare_selected_batch` and seeds the decode cache through
  `seed_experts_gpu_copy` (`ds4.c` 24608), which queues blits into
  `g_batch_cb`.
- **What V4.1 never runs.** `metal_graph_selected_async_load` (the load
  worker that calls `note_service_thread`) is reached only from
  `metal_graph_encode_decode_layer_phase`, the old `ds4_gpu_graph` decode that
  the layer-slice pipeline uses and V4.1 does not allocate. Every
  `on_service_thread()` guard is therefore inert here.
- **The pool** (`ds4_metal.m` ~12200-12300): one task per expert tensor
  (gate, up, down; 9.49 MiB per expert in total), `DS4_METAL_STREAMING_EXPERT_
  PREAD_THREADS` default 9, clamped to 18 and to the task count. Read-ahead
  (`F_RDADVISE` on `g_model_fd`) on by default, `DS4_METAL_DISABLE_STREAMING_
  EXPERT_READAHEAD` turns it off. Slabs on by default, 4096 MiB each
  (`DS4_METAL_STREAMING_EXPERT_SLAB_MB`), `DS4_METAL_DISABLE_STREAMING_EXPERT_
  SLABS` falls back to per-expert buffers. The timing summary
  (`DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY`) prints with the memory report,
  which the bench's `--cache-stats` prints after every frontier.
- **Diff state.** On `main` (`5410123`) `#1125`'s four commits, `a1afb82`,
  `f7695ea`, `8f5a745` and the `ds4_metal.m` part of `66f757b` apply in that
  order with `git apply --3way` and no conflict, and the result builds without
  warnings (tried in a scratch worktree, removed). Runtime lines: #1125 about
  250, `a1afb82` 62, `8f5a745` 96, `f7695ea` 53, `66f757b` 53. Every step is
  under 800.
- **#952 `a2e2ea53` against #1125.** Both rewrite
  `pending_load_release_buffers` to return reserved but uninstalled slots:
  `a2e2ea53` compares each load with the entry it would have filled, #1125
  nils installed loads in `pending_load_install` and returns what is left.
  Taking both returns a slot twice. #1125 covers every error path
  (`get_protected`, `load_selected_missing`, the pending load,
  `prepare_selected_batch`); `a2e2ea53`'s other three hunks guard the worker.
- **Measured baseline after `30`** (`perf-record.md` segment 1): decode 20.0
  t/s at 8K (50 ms a token), decode hit rate 0.90, cold-5000 hit rate 0.95.
  At 0.90, about 24 of a token's 240 expert lookups (40 layers, 6 experts)
  miss: about 230 MiB read per token, 0.6 missing experts (2 tasks of about
  3 MiB) per layer. The pool
  therefore runs at a queue depth of about 2-3 in decode, which is what
  `8f5a745` targets. Whether it is latency- or bandwidth-bound is S0's first
  measurement.
- **The harness** (`speed-bench/ab_bench.py`) has `--env` for both builds and
  `--b-bench-arg` for B, but no B-only environment. A switch can today only be
  measured with two trees that differ in a default.
- **Harness trap** (`perf-record.md`): the first run after a `--quality
  --ssd-streaming` CLI run takes about 800 s; no `--quality` run goes right
  before an invocation.

## Goals / Non-Goals

**Goals:**
- Know, from the pool's own counters, whether decode reads are latency- or
  bandwidth-bound on this SSD, before any knob is turned.
- Loading into the full 75 GiB cache without leaked slots, recycled in-flight
  blits or a pruning hang, bit-identical.
- Every read knob that exists or that the PRs add measured on this machine,
  with the winners made default and the losers deleted.

**Non-Goals:**
- The replacement policy (Belady at most about 6% of decode, `45` candidate),
  the per-layer id readback and the overlap of misses with GPU work
  (`50-ssd-miss-overlap`).
- `metal_graph`'s async load worker and the layer-slice pipeline (#952
  `a2e2ea53`, `next sync`).
- Tuning for machines other than this one: a default that wins here is the
  default, and the switch stays for others.

## Decisions

### D1. Five steps, each against the previous

- **S0, tool.** `a1afb82` (pool stats in the timing summary) and
  `ab_bench.py --b-env KEY=VALUE` (repeatable; B's environment only; the
  summary's `env` line names both sides, and a run with `--b-env` prints no
  record row, as a run with bench arguments already does), with one unit test
  in `tests/test_ab_bench.py`. Then a diagnosis run, not an A/B: the bench on
  `decode` and `cold-5000` with `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1`,
  recording `qd_avg`, `pool_gbps`, `task_gbps` and `wall_avg` in the record.
  Tool rule: bitwise, no metric below zero, against `main`.
- **S1, correctness.** #1125 `a0fe413`, `2cf7986`, `a6fc294`, `6c41f9b` as one
  step. Tool/correctness rule against S0. `a2e2ea53` is not taken (see
  Context).
- **S2, existing switches, no code.** On the S1 tree, A and B the same tree,
  B with `--b-env`: read-ahead off; slabs off; slab size 1024 and 16384 MiB;
  pread threads 4 and 18. A setting that wins becomes the default by a
  constant change, and the next sweep runs on that default.
- **S3, reads.** `8f5a745` (split preads, opt-in, default 1), swept at split
  4 and 8 with the S2 thread count, then threads 18 at the best split if
  threads were not already 18. The best becomes the default. If no split wins,
  `8f5a745` is reverted. Then `f7695ea` (the `F_NOCACHE` descriptor), swept at
  `DS4_METAL_STREAMING_EXPERT_NOCACHE=1`: default on if it wins (its switch
  inverted), reverted otherwise.
- **S4, residency.** `66f757b`'s `ds4_metal.m` part, swept at
  `DS4_METAL_STREAMING_SLAB_RESIDENCY=1`: default on if it wins (the switch
  becomes `DS4_METAL_DISABLE_STREAMING_SLAB_RESIDENCY`), reverted otherwise.
  Its bench, its M2 Ultra CSVs and its test are not taken; if it is kept, its
  `tests/test_metal_slab_residency.m` is.

Alternative: port every code step first and sweep once at the end. Rejected:
the knobs interact (split raises the task count the thread limit caps;
`F_NOCACHE` turns read-ahead off), so each sweep runs on the defaults the
earlier ones chose.

### D2. Which metric decides

Target metrics: `decode 8192` (the miss path in steady decode), `append +300`
(a token-major append) and `ttft 5000` (a sweep plus a 904-token tail). A
setting or step is kept when the pooled 95% CI of at least one of the three
lies above zero and no throughput metric's pooled CI lies wholly below zero.
`guard-decode` runs once per invocation as the guard. Three targets raise the
chance of a false keep, so a keep always needs two pooled invocations, never
one.

A setting whose first invocation has a point estimate at or below zero on all
three targets is dropped without a second one: not keeping it changes
nothing.

### D3. Invocation shape

`--kinds decode,append,cold-5000 --guards guard-decode --bitwise --budget
2700`: warm-ups, one full A B B A quad of each kind (about 1070 s), a second
if the budget allows, then the guard. Code steps run with `--a` the previous
step's tree; sweeps run with `--a` and `--b` the same tree and `--b-env`.
Previous-step trees are worktrees with the step's files copied in, unless the
owner authorizes local commits on the change branch.

### D4. Correctness evidence

- `--bitwise` on every invocation: tokens and logits after every prefill and
  decode frontier.
- Expert-cache counters equal between A and B. No step changes what the cache
  keeps, with one possible exception: `2cf7986` marks seeded GPU-copy entries
  in flight, so `take_reusable` may skip one it used to recycle. If S1's
  invocation drops pairs for cache drift, it is rerun with
  `--cache-policy-change` and the drift recorded.
- `make test-metal-ssd-experts` after S1, S3 and S4 (model-less, runs the
  slab and selected-load fixtures).
- A regression test for `6c41f9b` in `tests/test_metal_ssd_experts.c`: seed
  entries by GPU copy inside an open batch (in flight after `2cf7986`), lower
  the budget below the entry count, and require the prune to return with the
  in-flight entries intact. Taken if the fixture can reach it in about 40
  lines; otherwise recorded as not tested.
- `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` at the
  end.

### D5. Page cache between runs

The harness alternates A and B in one page cache. A run with cached preads
leaves expert pages behind for the next run; an `F_NOCACHE` run does not, so
in `A B B A` the second A inherits a colder page cache than the first and the
comparison favours B. For the `F_NOCACHE` sweep, A's medians are compared with
A's medians of the previous invocation on the same tree: if A is slower by
more than the A/A noise (±1.6%), the verdict is recorded as biased and not
used to keep the setting.

### D6. Docs and registry

- `speed-bench/README.md`: `--b-env`; the pool-stats line of the timing
  summary.
- `AGENTS.md` ("the knobs worth knowing"): any default this change moves.
- `speed-bench/perf-record.md`: the S0 diagnosis, a row per sweep, the
  change's row against the segment start.
- Registry: #570 `a1afb82` (adopted); #1125 (adopted, `next sync` removed);
  #952 `a2e2ea53` (`next sync`: the worker, which V4.1 does not run; the slot
  return superseded by #1125); #621 `8f5a745`, `f7695ea` and #1033 `66f757b`
  (kept or dropped, with the numbers); #533 (the read-ahead sweep's answer).

### D7. Scope after S0's diagnosis (2026-09-29)

S0's Read path (`perf-record.md`) shows the reads and buffer preparation are
about 4 ms of a 52 ms decode token and of a token-major tail step; `sync`
(38.9 ms) is GPU work and does not grow with misses. The pool runs at
`qd_avg` 2.2 with `workers_avg` 3.3. What each planned item can still win:

- **Read-ahead off: kept.** Situation 0 timed the `F_RDADVISE` calls at
  1.8 ms of a decode token on the eval thread, and the reads are served warm.
- **Split preads: kept, split 4 only.** It is the one knob that shortens the
  0.5 ms dispatch; split 8 only if 4 wins.
- **Residency set: kept.** Per-submission residency work lands inside `sync`,
  the only large term.
- **Pread threads: dropped.** The limit of 9 never binds (3.3 workers per
  dispatch); 4 or 18 cannot change a decode dispatch.
- **Slabs off, slab size: dropped.** They change allocation shape, not read
  time; slabs off multiplies the buffer objects the residency step is about.
- **`F_NOCACHE`: dropped unported.** The reads run at 9-10 GB/s per task
  because the page cache serves part of them; the descriptor gives that up,
  and D5's bias would make its A/B hard to trust.

The dropped items go to the registry as history with these numbers.

## Risks / Trade-offs

- [A sweep favours whichever build runs second] → A B B A order; the A/A
  noise of the segment start (±1.6%) as the floor; two pooled invocations per
  keep.
- [`F_NOCACHE` biases the page cache the next run inherits] → D5.
- [A default tuned here hurts smaller machines] → the switch stays, and
  AGENTS.md names it.
- [#1125 changes a victim choice and the cache counters drift] → D4.
- [The residency set depends on macOS 15 or later] → the `@available` guard
  stays; the record states the macOS version it was measured on.
- [Nine or more invocations of about 45 minutes each] → the diagnosis first:
  if the pool reaches the SSD's bandwidth at `qd_avg` near the thread limit,
  the split sweep is cut to one invocation at split 4.
- [Sync conflicts] → upstream's text for every ported hunk; the only child
  edits are default constants and, for a kept opt-in, the inverted switch
  name at one site.

## Migration Plan

Additive; each default a change moves keeps its switch. Rollback is a revert
of the squash commit.

## Open Questions

- Whether the SSD is latency- or bandwidth-bound in decode. S0 answers it
  before S2; it can shorten the sweeps but does not change the steps.
