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
