# Design

## Context

- **Three sites.** ds4 today steers at `ffn_out`
  (`metal_graph_apply_directional_steering_ffn`, pre-residual, pre-HC-expand) and
  `attn_out`. msuiche's V4.1 vector lives at `residual_stream_post_layer`: the
  post-layer HC fold (mean over the 4 hc copies) to a single 5120 stream, pre-engram.
  These are different points in the stream; a vector is only valid at the site it was
  measured.
- **HC structure.** V4.1 has `hc_mult=4`. The graph carries `hc_expand_*` tensors
  (`ds4.c:12331-12337`: `hc_expand_comb`, `hc_expand_post`, `hc_expand_residual`,
  ...). Engram is read on layers {1,14} (`ds41_engram_layer`). The hook site is the
  single-stream residual after the HC comb/fold and before the engram read.
- **distributedcognition** uses a different site again (weight edits on `attn.wo_b`
  + `ffn.shared_experts.w2`, direction measured at the `attn_norm` input). That
  source is `404`'s concern; this change is msuiche's site.
- **Converter target.** The runtime loads a flat `.f32`,
  `directional_steering_layer_count()` (40) x `n_embd` (5120), via
  `read_f32_binary_file`. 40 x 5120 x 4 = 819200 B, matching msuiche's ~800 KB after
  the layer-0 zero pad.

## Goals / Non-Goals

**Goals:**
- A steering point that matches the vector's declared hook, so msuiche's published
  removal reproduces.
- A converter that is exact about layer indexing and carries the hook/alpha metadata.

**Non-Goals:**
- Fusion with distributedcognition (`404`), decay/phase schedules (`403`), the
  quantitative framework (`402`). This change lands the site and a coarse manual
  check.

## Decisions

### D1. A new application point, not a repurposed ffn hook
- Add `residual_stream_post_layer` as its own steered site. Keep `ffn_out`/`attn_out`
  for `ffn_out_pre_residual`-style vectors (the 0731 GLP namespace). A vector's
  sidecar names its hook; a mismatch is refused.

### D2. Locate the fold tensor (the model's own reduction)
- The site is the post-HC-fold single 5120 stream, pre-engram. msuiche's GGUF is
  precise: it is "the mean over the 4 hc copies (**the model's own aux-hidden-state
  reduction**)" — the architecture's existing reduction, not an invented mean. In ds4
  that is the output of the HC fold that produces the next sub-block's single stream
  (`ds4_gpu_hc_split_weighted_sum_norm_tensor`, `ds4_gpu_hc_expand_*`;
  `metal_graph_after_attn_hc`/`after_ffn_hc` are `hc_dim`-wide, `metal_graph_flat_hc`
  the flattened view; `hc_expand_comb`/`hc_expand_post` at `ds4.c:12336-12337`).
  Investigation: confirm which graph tensor is that reduced single-5120 stream, taken
  before the engram read on layers {1,14}, and that applying the projection there
  reproduces msuiche's removal (3.2 / `402`). It goes in for the decode and the
  prefill/token-major phases, layers 1-39.

### D3. Reuse the existing projection
- `ds4_gpu_directional_steering_project_tensor` already does `y -= scale*d*dot(d,y)`
  per layer on a 5120-wide tensor. Bind it at the fold site; the CPU reference
  mirrors with `cpu_directional_steering_project_rows`. No new kernel unless the fold
  tensor is not directly addressable.

### D4. Converter and sign
- `direction.N -> layer N`, layer 0 zeros (no `direction.0`). Unit-norm preserved.
  ds4 `--dir-steering-residual +alpha` reproduces msuiche's `h -= alpha*(h.d)d`. The
  converter reads the GGUF metadata keys `controlvector.layer_count`,
  `controlvector.model_hint` (must be `deepseek_v41`), `glp.hook_point` (must be
  `residual_stream_post_layer`), `glp.alpha_default` and `glp.content_sha256`, and
  copies them plus the base revision and the non-monotone / L1-6 caveats into the
  `.json` sidecar.

## Risks / Trade-offs

- **[Wrong fold tensor]** -> the vector is misapplied and removal does not reproduce.
  Mitigation: the acceptance check is behavioral (a few prompts the base refuses are
  answered at alpha 0.5; `402` quantifies against msuiche's refusal32 24/32 and
  distributedcognition's 17->1 judge). Confirm the tensor by matching the published
  direction of removal before trusting the site.
- **[Non-monotone alpha, L1-6 below the null gate]** -> do not raise alpha blindly;
  0.5 is the knee, 2.0 regresses and code-switches. Carried in the sidecar/docs;
  `403`/`405` handle dose.
- **[Gated download]** -> the vector needs the user's `HF_TOKEN` and acceptance of
  both Responsible Use Agreements; the converter and the hook are testable on a
  synthetic vector without it.
- **[Enabled-path cost]** -> one extra 5120 projection per layer when on; disabled
  path bitwise and zero-cost (no tensor). Measured once, not a perf change.

## Investigation findings (2026-10-13) — supersedes the tensor cites above

A full read of the graph (subagent map, confirmed against the source) corrects the
Context section: the symbols it cited (`metal_graph_*`, `ds4_gpu_hc_split_weighted_sum_norm_tensor`,
`hc_expand_comb/post/residual` at `ds4.c:12331-12337`) all belong to the **legacy
DeepSeek V4 graph** (`struct ds4_gpu_graph`), which is **dead for V4.1**:
`ds4_session_create` (ds4.c:31490-31531, `#ifdef DS4_HAS_DEEPSEEK41_GPU`) allocates
only `s->ds41_graph` and returns before touching `s->graph`; decode dispatches
`ds41_graph_step` (ds4.c:32912). All existing ffn/attn steering hooks also live on the
dead graph. So the residual hook is a genuinely new application point on the **active
`ds41_*` graph** (`struct ds41_gpu_graph`, ds4.c:23150), and the ffn/attn hooks are a
template to COPY.

**The fold tensor.** The single 5120 stream is `g->x` (DS41_SCRATCH, 5120), produced
by the HC weighted-sum fold inside `ds41_hc_mix` (ds4.c:23575-23602). The 4-copy
residual is `g->residual` (4*5120=20480). `ds41_hc_mix` runs **twice per layer**:
before attention (`ffn=false`, ds4.c:23904) and before ffn (`ffn=true`). A once-per-layer
`residual_stream_post_layer` edit must apply on **`ffn==false` only** (the layer-input
fold ~= the previous layer's output), else it fires twice.

**Two blockers the current architecture imposes:**
1. **Fused with norm.** In both fast paths (`ds4_gpu_dsv41_hc_block_input_rows` 23584,
   `ds4_gpu_dsv41_hc_input` 23594) the fold `g->x` and the rms-norm `g->norm` are ONE
   kernel; `g->x` is consumed internally and not carried forward (the carried state is
   `g->residual`, rebuilt by hc_expand). A projection inserted after the fused kernel has
   **no effect**. `g->x` is addressable as a standalone tensor only on the **slow path**
   (ds4.c:23598-23601), between `ds4_gpu_hc_weighted_sum_bf16_tensor` (23600) and
   `ds41_norm` (23601). So the edit must force the slow path when steering is on.
2. **Engram after, not before, the fold.** `ds4_gpu_dsv41_engram_add` (ds4.c:23900,
   layers {1,14}) mutates the 4-copy `g->residual` BEFORE the fold at 23904. No single
   5120 stream exists pre-engram. So "post-fold **pre-engram**" is unsatisfiable by an
   existing tensor; applying at `g->x` is **post-engram on layers 1 and 14** (and clean
   on the other 38, which have no engram).

**Decision A vs B (needs the owner):**
- **A (recommended).** Force the slow `ds41_hc_mix` path when `directional_steering_residual
  != 0 && !ffn`, and project `g->x` between 23600 and 23601 with the existing
  `ds4_gpu_directional_steering_project_tensor(g->x, dirs, il, DS4_N_EMBD, 1, scale)`. No
  new kernel. Deviates from msuiche only on layers 1/14 (post- vs pre-engram); those sit
  below msuiche's own null gate (L1-6) so the deviation is likely immaterial. The off
  path (scale 0) stays on the fast fused kernels -> bitwise identical.
- **B.** Project the 4-copy `g->residual` BEFORE `engram_add` with a NEW per-copy kernel
  (applies the direction to each of the 4 hc copies). Truly pre-engram, but a new kernel
  and 4x application semantics to validate.

**Concrete plan for A** (not yet implemented — awaiting the A/B go-ahead; it is a wide,
delicate hot-path change landed with the owner's eyes on it, not blind overnight):
1. Frontends + option/field: `--dir-steering-residual F` in ds4_cli.c / ds4_server.c /
   ds4_help.c (set `directional_steering_scale_set = true` so a file does NOT also
   default `ffn=1`); `float directional_steering_residual` in `ds4_engine_options`
   (ds4.h); engine `directional_steering_residual_scale` + copy in ds4_engine_open.
2. Upload the per-layer directions as a `ds41_gpu_graph` tensor in `ds41_graph_alloc`
   (mirror the `engram_q_norm[]` upload), gated on a non-zero scale (no tensor when off).
3. Thread `il` into `ds41_hc_mix`; when `scale != 0 && !ffn` skip both fused paths and
   project `g->x` on the slow path (23600->23601).
4. Mirror on the prefill/batch folds: `ds41_before_attention_batch` (b->x fold, 23959-61)
   and `ds41_decoder_prepare` (active.x, 24605) — before-attention fold only.
5. CPU reference: `cpu_directional_steering_project_rows(scratch->attn_cur, dirs, il, 1,
   scale)` right after the fold at ds4.c:11595 (CPU has no engram, so no ordering issue).
6. `DS4_METAL_DISABLE_V41_RESIDUAL_STEERING` classified in ds4_env.def (read at the apply
   site, so env-check passes).

**Index/sign to confirm behaviorally.** `404`'s offset search found msuiche and distcog
align best at a **+1** layer offset (distcog measured at the layer-input fold), so
msuiche's `direction[N]` may map to the before-attention fold of layer `N` or `N+1`; the
drop-in check (task 3.2) at alpha 0.5 settles the index, sign and whether A reproduces the
removal. The converted vector (`v41-msuiche.f32`, 401 task 1) is ready for that test.
