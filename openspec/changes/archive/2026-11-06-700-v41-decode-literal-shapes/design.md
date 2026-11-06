# Design

## Context

See proposal.md for why. What the read of `b66c926` and `e99dc21` against the
`b3f5018` sync tree found:

- The paired q_a/kv projection is called from `ds41_attention` (`ds4.c`, the
  paired-projection call) and dispatched in `ds4_metal.m` with `nr0` fixed at
  2. Upstream's literal kernel instantiates `kernel_mul_mv_q8_0_f32_rope_impl`
  with a `ROPE_IN` template parameter this child's `metal/dense.metal` does
  not have, so the template arguments need adapting.
- The output-B expand is called with `add = NULL` on every decode layer and
  dispatched through the HC expand path in `ds4_metal.m`.
- The Engram gate kernel `kernel_dsv41_engram_add` in `metal/dsv41.metal` is
  identical to upstream's base, and its call has `!mask && width == 5120 &&
  rows <= 16` on decode.
- Upstream reads its switches through a `ds4_gpu_v41_on` bitmask and counts
  kernel runs for its tests. This child reads plain `getenv` switches
  classified in `ds4_env.def`, and has no kernel-run counter.

## Goals / Non-Goals

**Goals:**
- Bitwise-identical output with and without each switch.
- A combined A/B against the sync tree on decode and the short kinds.

**Non-Goals:**
- The MXFP4 MoE literal and the FFN-join literal (unreachable by default).
- `4ff3af6` (moved to `690`), `a50fecc` + `04c0867`, `0f9b03c` (dropped).

## Decisions

- **Kernels verbatim, dispatch by hand.** Kernel bodies are copied from
  upstream; only the template arguments the child's base lacks are adapted.
  The host gates are written in the child's existing dispatch functions.
  *Alternative:* cherry-pick. It conflicts with change `70`'s dispatch code.
- **Upstream switch names, plain getenv.** Same names as upstream so a later
  sync matches them; read once like the child's other decode switches.
- **The Engram gate is conditional.** Its exactness depends on reproducing the
  compiler's fma contractions. The kernel test runs first on this machine; if
  any output differs, the kernel is dropped from the change and the decision
  recorded.
- **Measurement.** One `ab_bench.py --kinds decode,cold-2500,append --bitwise`
  run against the sync tree, B = this change. The change is under 800 lines, so
  the intake rule is "no metric below zero"; with an expected gain of a few
  tenths of a percent, a neutral result drops it.

## Risks / Trade-offs

- **[Below resolution]** The gain may not be measurable. -> A neutral A/B
  drops the change; the drop is recorded in perf-record's rejected ideas.
- **[Template drift]** The adapted template arguments could pick a different
  arithmetic path. -> The kernel test compares with the generic kernel bit for
  bit before any A/B.
