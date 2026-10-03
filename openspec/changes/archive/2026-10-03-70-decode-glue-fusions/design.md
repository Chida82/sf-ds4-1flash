# Design

## Context

See proposal.md (Why). Facts from the code and the diffs:

- **The start gate is met.** `perf-record.md`'s Read path, after `40`, puts
  36-41 ms of a 45-47 ms decode token in `sync`: the GPU finishing the
  layer's queued work up to the router. That is GPU time, and it does not
  grow with misses. The reads and buffer preparation are about 4 ms.
  `ds41_graph_layer` (`ds4.c` ~24477) issues about 60 dispatches per layer
  on one box, matching #1073's count. The glue is therefore most of what is
  left to shorten in decode, and in the token-major tails behind
  `ttft 2500` (452 tokens) and `ttft 5000` (904 tokens).
- **The PR.** #1073 is still open at `3d3c83b`, based on `0aaea5a`, the
  child's merge-base. The head is fetched as `refs/sfpr/1073`. The commits
  this change takes, in PR order, are `d95f8b6` (2), `edceb7a` (3),
  `e768396` (5), `d8d1523` (12), `4fbbc4a` (13), `1923131` (16) and
  `a3f6f31` (17).
- **Applicability.** A `git apply --check -C1` dry run against `main`:
  - `e768396`, `edceb7a` and `a3f6f31` apply;
  - `d95f8b6` fails at one `ds4_metal.m` hunk (the child's pruned file);
  - `4fbbc4a` and `1923131` fail because they build on `d8d1523`. The head
    half of `4fbbc4a` edits `d8d1523`'s `ds41_graph_after_moe(..., carry)`,
    and `1923131` fixes `d8d1523`'s `kernel_dsv41_rope_quantize`. The
    proposal's S4 pairing of `d95f8b6` with `1923131` is therefore wrong:
    `1923131` goes with the rope store.
  - `d8d1523` fails in 7 files.
- **`d8d1523` is 4.1K lines, but the DSpark code is separate.** About 1.2K
  lines are in `ds4.c`. The DSpark part is the `ds41_draft` struct, its
  rings, the verify-row bookkeeping and `ds4_gpu_dsv41_verify_rows`. Each
  decode fusion is a separate function with a fallback to the unfused
  kernels: `ds41_hc_mix`, `ds41_attention_project`, `ds41_rope_store`,
  `ds41_attention`, `ds41_attention_low`/`_expand`, `ds41_moe_partial`,
  `ds41_graph_after_moe`. Each has a one-row Metal entry point. The `_rows`
  forms and the `count <= DS4_TP_BATCH_MAX_ROWS` call sites in the batch
  functions serve DSpark verify, TP small prefill and batched sessions. The
  child no longer defines `DS4_TP_BATCH_MAX_ROWS`.
- **What the fusions gate on.** The Q2 GGUF's attention, shared-expert and
  head matrices are Q8_0, the HC mixers F16 and the router F32, so every
  single-token fused path is reachable here. The MXFP4/Q4_K and
  `PRE_M5_*` paths are not.
- **The switches upstream gives.** `DS4_METAL_DISABLE_V41_HC_BLOCK_INPUT`,
  `_EXPAND_FUSION`, `_ROUTER_ONE`, `DS4_METAL_DISABLE_GATHERED_KV_STAGE`,
  `DS4_METAL_DISABLE_FLASH_HEAD_SHARE` and
  `DS4_METAL_DISABLE_M5_HC_NORM_MIX_CLUSTER2`. The paired projections,
  pair norm, q_b+RoPE, rope store, low+inverse RoPE and shared SwiGLU have
  none.
- **The control test.** `a3f6f31`'s `check_decode_control` runs a control
  session with one switch set and a candidate without it. It compares
  logits, Engram history and every KV state span (`ds41_state_spans`, still
  in the child) over 65 decode steps after 511- and 2047-token prefixes. It
  opens the engine resident (`ssd_streaming = false`), which cannot load on
  128 GB.
- **The current decode loop** (`ds41_graph_step` ~24547) reads both Engram
  tables synchronously before the first command buffer. It queues the
  layers, flushing without waiting, and drains at layer 13 and at the last
  layer (`30`). `ds41_graph_logits` then opens a separate command buffer for
  the head and waits on it.

## Goals / Non-Goals

**Goals:**
- Fewer single-token decode dispatches per layer, with identical bits.
  Every step's output is bitwise identical to the previous step at every
  harness frontier and in every generated token.
- One verdict per fusion site. A site that does not pay is not carried by
  the others.

**Non-Goals:**
- The `_rows` forms and their batch call sites (DSpark verify, TP small
  prefill, batched sessions). They are not reached in the measured mode,
  and they change paths nothing here can measure.
- TP: every TP branch keeps upstream's unfused path (`g->tp_world == 2`),
  as in `d8d1523`.
- The MXFP4/Q4_K, `PRE_M5_*` and `MOE_DEDUP` paths, the MMA rows
  (`262b4a6`, `a6b50ff`: `drop: output`) and all DSpark code.
- Prefill sweeps: `d8d1523`'s sweep hunks are DSpark capture or batch rows.

## Decisions

### D1. Steps and order

The order follows the PR's commit order, which the text dependencies
require:

| Step | Commit | What | Kind |
|---|---|---|---|
| S0 | `a3f6f31` | `--decode-switch` control test, opened with `--ssd-streaming` | tool |
| S1 | `e768396` | skip candidate selection while every block is kept | small |
| S2 | `edceb7a` | experts selected in one dispatch (`kernel_dsv41_router_one`) | small |
| S3 | `d95f8b6` | BF16 rounding inside the producing kernels (single-row decode sites only) | small |
| S4a | `d8d1523` | HC block input: mixer + split + weighted sum + norm in one dispatch, with the M5 cluster2 variant | site |
| S4b | `d8d1523` | attention projections: paired Q8_0 q_a/kv, pair norm, q_b with RoPE | site |
| S4c | `d8d1523` + `1923131` | RoPE + quantize + store into the KV, index and compressed rows | site |
| S4d | `d8d1523` | staged attention gather and flash head share | site |
| S4e | `d8d1523` | low projection with inverse RoPE; attention output and shared down fused into the HC expand | site |
| S4f | `d8d1523` | shared gate/up SwiGLU in one dispatch | site |
| S4g | `d8d1523` | asynchronous Engram start/finish, and the F16 rounded projection | overlap |
| S5 | `4fbbc4a` | head half: the vocabulary head encoded before the last drain | overlap |

S4a-g is `d8d1523` cut by call site. Each site is a function with its own
fallback, so it can be dropped alone. The order inside S4 follows the
layer: each step's diff context is the previous step's result.

Each step is an uncommitted diff on the branch. Its A tree is
`../sf-ds4-1flash-base` (a detached worktree of `main`) with the previous
kept steps applied and rebuilt, as in `60`.

Alternative: `d8d1523` as one step over 800 lines, needing +1.5%. Rejected.
One verdict for nine fusions would keep a site that costs time when the
others pay, and drop the ones that pay when one breaks bits.

### D2. Kernel text from the PR head, call sites from `d8d1523`

Metal kernels and their `ds4_metal.m` entry points are taken from `3d3c83b`.
That includes `0ac42d6`'s, `8be1005`'s and `a15028e`'s edits to those
functions: the head state is what a future sync meets. The `ds4.c` call
sites are the single-token sites listed in Context.

The child calls a rows-form entry point with one row where the head has
folded the one-row form away (`8be1005`). DSpark identifiers, `_rows` call
sites and verify flags are cut, each with an `sf-ablate(dspark)` marker.
CUDA files are absent.

Alternative: `d8d1523`'s own text. Rejected: it leaves the one-row forms
that `8be1005` removes, so every later sync conflicts on them.

### D3. Bitwise proof

Bitwise identity is checked at three levels:

1. **The harness `--bitwise`, every step.** It compares logits at each
   frontier and every generated token. `cold-2500`'s 452-token tail and
   `append +300` run through the decode graph, so a frontier dump covers
   hundreds of fused decode steps. These kinds are therefore in every
   step's set (D4).
2. **`--decode-switch`, where a switch exists:**
   - S2: `_ROUTER_ONE`;
   - S4a: `_HC_BLOCK_INPUT` and `_M5_HC_NORM_MIX_CLUSTER2`;
   - S4d: `GATHERED_KV_STAGE` and `FLASH_HEAD_SHARE`;
   - S4e: `_EXPAND_FUSION`.

   S0 ports the test with `ssd_streaming = true` and the child's prompt
   reader. It also adds a `test-deepseek41-decode-switch` make target that
   runs it for one switch.
3. **Unit tests for the arithmetic traps:**
   - S2: the router against the bitonic `ds4_gpu_router_select_tensor`, on
     forced ties, an all-equal round, all logits at -120 (the polynomial
     softplus branch), ±0 and denormals;
   - S4c: `c6f4086`'s rope-quantize case.

   Both go in `tests/test_deepseek41_metal.c`.

No switch is added for the sites without one. Level 1 already drives the
fused kernels through hundreds of decode steps. A switch would be
permanent code kept only for a test.

### D4. Keep rule, kinds, invocations

Each step runs against the previous one with `--bitwise`, `--budget 3600`
and `--kinds decode,append,cold-2500`. The guards are `guard-decode` and,
from S4g on (Engram reaches prefill too), `cold-5000`.

| Step | Targets |
|---|---|
| S0 | none: tool rule (bitwise, no metric below zero) |
| S1-S4f | `decode 2048`, `decode 8192` |
| S4g, S5 | `decode 2048`, `decode 8192`, `append +300` |

`ttft 2500` is reported for all steps and is not a separate target: its
tail is decode.

The keep and neutral rules are the context's. Each step is under 800
runtime lines (tests do not count); a step that grows past 800 needs
+1.5%. A second invocation, pooled with the first, runs unless the first
is a drop or every target's 95% CI lies wholly above zero. The owner
amended this for `70` alone, after S3: under the earlier rule (no second
invocation only if a target's lower bound clears +1.6%), S2 and S3 each
spent an hour on a second invocation that confirmed the first. S4's
cumulative +1.5% check and the record row remain the net against a
session that drifted.

S4's kept sites add up to more than 800 runtime lines. They must also pass
+1.5% together, from one invocation of the last kept S4 tree against the
S3 tree. If that fails, the smallest kept sites are dropped until the rest
passes.

Decode steps do not change which sweep seeds the cache, so
`--cache-policy-change` is not used. A dropped pair is reported, not
re-run.

### D5. S4g and S5 are scheduling steps

S4g starts the two Engram reads before the first command buffer and joins
each one just before its table is written: layer 1, and layer 14 after the
layer-13 drain. S5 encodes the head in the last layer's command buffer
instead of a separate begin/end. Both change overlap, not arithmetic, so
they are decided on the harness alone.

S4g's reader uses `ds4_engram.c`'s existing thread pool (`d8d1523`'s
`prefetch_thread`). `120` builds on it.

### D6. Docs, registry, record

Registry:
- the #1073 lines for the seven commits, each with its step verdict and
  numbers;
- `1923131` moves from "S4" to S4c;
- `c6f4086` is noted as taken in part (the test only);
- `0ac42d6`, `8be1005` and `a15028e` read "the hunks D2 takes".

`perf-record.md` gets each step's pooled rows and the change's row against
the segment start. `AGENTS.md` gets:
- the switches that remain;
- a line in "SSD streaming is not optional" on the dispatches per layer;
- the `--decode-switch` target among the model-backed checks.

## Risks / Trade-offs

- [A fused kernel rounds differently on M5 than on the M3 Ultra / M4 Pro it
  was proven on] → bitwise is required at every step. The site is dropped
  alone and recorded `drop: output` with the frontier or the switch that
  differed.
- [`1923131`'s explicit `fma` depends on the compiler] → the rope-quantize
  unit test compares bits against `kernel_dsv41_rope` + quantize. If it
  fails, S4c is dropped.
- [The router's tie order differs from the bitonic network] → D3's
  forced-tie test runs before any harness run.
- [Fusing the work removes overlap: one fused kernel per layer can be
  slower than several small ones that run concurrently] → per-site
  verdicts (D1). This is the case in which a site is dropped.
- [S4g's asynchronous reads race the layer-13 drain, or a cancelled
  session leaks a reader] → the short review traces both paths, and
  `make test` runs `test_engram`. `d8d1523`'s join is at the table's first
  write.
- [A large permanent conflict surface with upstream until #1073 merges] →
  accepted by the owner's rule. D2 takes the head's text to keep the sites
  where the next sync expects them.
- [The decode-switch test needs about 64 GB of expert cache and loads the
  model twice per prefix] → it runs once per switch step, outside the
  harness, never during an A/B.

## Migration Plan

The upstream switches turn off S2, S4a, S4d and S4e at runtime. The other
sites fall back only by revert. Rollback is a revert of the squash commit.
