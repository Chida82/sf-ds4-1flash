# Design

## Context

The only live V4.1 steering site is the weighted HC attention-input fold after Engram
(`v41_attn_input_weighted_fold_post_engram`, revision 2): `h -= s·dot(d,h)·d` with a
per-layer unit direction `d` (`401`). Three code paths reach it: the token-major decode
graph (`ds41_hc_mix`, `g->x`), the prefill batch (`ds41_before_attention_batch`,
`b->x`) and the decoder suffix (`active.x`). A short prompt at `n=1` never decodes: its
first token comes from the token-major prefill, which exposes `g->x` only on the slow
fold path.

The code described here exists (commits `8daabe6`, `ac2cdca`, `f70f42c`). This design
records what it computes and what it guarantees.

## Goals / Non-Goals

Goals: a second constant-scale direction at the same site with the same gate, disable
and persistence rules; an exact statement of when two folds are a subspace removal; a
bounded, output-neutral activation capture; reproducible rank-2 identity in the harness.

Non-goals: a `403` schedule for the second direction; rank > 2; a release-grade probe
with measured overhead (`405` 1.1–1.3 remain the place for that); any new default
vector (`406`); any claim about which second source works (`404` closed msuiche ×
abliteration negative; `409` owns the next operator family).

## Decisions

### D1. Second fold, same site, same guards

The second direction is loaded by the same matrix loader as the first (40 rows × 5120
f32, row 0 zero, unit rows within 1e-2) and applied as an in-place fold immediately
after the first at each of the three routes. It shares the opt-in gate, the disable env
and the persistence refusal; the server skips `--kv-disk-dir` when either direction is
active. A second file without the opt-in is refused with the same message as the first;
a second file with zero second scale is not loaded and the run is bitwise the
single-direction run.

### D2. Composition is exact only for orthogonal directions

For per-layer unit `d₁ ⟂ d₂`, two sequential folds at scales `s₁, s₂` equal removing
the projections onto the two axes independently, so at `s₁ = s₂ = 1` they null the 2-D
span. For non-orthogonal pairs the second fold sees `h` already edited by the first:
the shared component is removed twice and the result depends on order. This is what
sank msuiche + abliteration (cos 0.72). The run identity therefore carries the
per-layer cosine between the two loaded directions, and documentation calls the
intervention "two sequential folds", reserving "rank-2 span removal" for pairs whose
median cosine is below the documented threshold. The runtime does not refuse
non-orthogonal pairs — a researcher may want sequential removal — it only records them
honestly.

### D3. Capture at the application point, not a legacy hook

`DS4_V41_DUMP_STEER_INPUT=<path>` writes the *pre-edit* fold input so that a direction
derived from it is derived at the exact row the fold edits (capture row *k* =
application row *k*, settling the layer-id question of `405` 4.5 for own-derived
vectors). Correct GPU readback requires the `ds4_gpu_synchronize()` → read →
`ds4_gpu_begin_commands()` bracket, and `ds4_gpu_tensor_read` returns nonzero on
success — both were missed once and are now the reference pattern. On the token-major
route the env forces the slow fold path so `g->x` is materialised; this is the cost of
a probe that is not meant for release. Unset, the only work is one `getenv` per fold.

### D4. Harness identity

A rank-2 arm records `rank2 = {file2 hash, scale2}` inside the intervention identity;
`run.py` refuses `--steer2` without `--steer` and nonzero `--residual2`. A manifest
without `rank2` is a rank-1 run; the two never share a cache key.

### D5. Extraction is a contrast, not an oracle

`extract_floor_direction.py` computes `unit(mean_A − mean_B)` per layer from captures
at base. A strongly separating direction is not thereby a causal opener (`405`
Results): it is a candidate for `402`, nothing more. The sidecar records classes,
counts, per-layer raw norms and the f32 hash so a later run can tell which capture a
vector came from.

## Risks / Trade-offs

- [Second fold mistaken for a span removal] → cosine in the identity, "sequential
  folds" wording, D2.
- [Capture perturbs timing or output] → output unchanged by construction (read before
  edit); it is slow and says so; never set in a measured run.
- [Flags look like a shipped feature] → gated exactly like the first direction;
  no default vector; documented as research runtime in `AGENTS.md` Identity.
- [Rank-3 creep] → out of scope; a third direction needs its own measured case first.

## Migration Plan

Nothing migrates: the off path is unchanged and a run without the second flags has the
same identity as before. Landing is documentation plus the verification tasks below.
