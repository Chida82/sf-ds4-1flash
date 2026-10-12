# Tasks

Depends on `400` (gate opt-in). Prerequisite for the drop-in check (3.2): the user
sets `HF_TOKEN` and accepts the Responsible Use Agreement on both repos; downloads go
to `/tmp`.

Status 2026-10-13: Group 1 (converter) DONE. Group 2 investigation (2.1) DONE in
`design.md`. Option A IMPLEMENTED for the DECODE path and verified: build clean, `make
test` EXIT=0 (env-check 503, the new `DS4_METAL_DISABLE_V41_RESIDUAL_STEERING`
classified), OFF path (`--dir-steering-residual 0`) BITWISE IDENTICAL to baseline on a
benign prompt, ON path (0.5) alters the residual and stays coherent (effective, benign).
Remaining: the PREFILL/BATCH fold coverage (`ds41_hc_mix_batch`) and the CPU reference
mirror (2.3), and the refusal-efficacy drop-in via `402` (3.2). Index chosen = direction
`[il]` at the before-attention fold of layer `il`; the +1 analysis means `402` may show a
one-layer shift is better (a one-constant change). Layers {1,14} apply post-engram (minor,
below msuiche's null gate).

## 1. Converter

- [x] 1.1 `dir-steering/tools/controlvector_to_f32.py`: reads a GGUF `controlvector`,
  asserts arch `controlvector` + `model_hint deepseek_v41` + `hook residual_stream_post_layer`
  and 39 `direction.<N>` (fp32, 5120, unit norm), writes `.f32` 40x5120 (L0 zeros,
  `direction.N`->layer N) and a `.json` sidecar (hook, `alpha_default`, `content_sha256`,
  base revision, provenance, non-monotone/L1-6 caveats). Self-check on a synthetic
  GGUF fixture asserts bytes + indexing exact. Confirmed end-to-end on the real msuiche
  GGUF: 819200 B, all 39 rows L2 norm 1.0000.
- [x] 1.2 Refuses a mismatched vector: wrong arch, wrong model_hint, wrong hook, missing
  `direction.1`, wrong width, or a non-unit row past tolerance — each exits naming the
  cause (all six verified in the self-check).

## 2. Residual-stream hook

- [x] 2.1 Located the site in the ACTIVE `ds41_*` graph (not the dead `metal_graph_*` V4
  graph the proposal cited): the single 5120 fold is `g->x`, produced in `ds41_hc_mix`
  (ds4.c:23575-23602); the once-per-layer `residual_stream_post_layer` edit maps to the
  before-attention fold (`ds41_graph_before_attention` 23904, `ffn==false`). Decode,
  prefill/batch and CPU call sites, the fused-with-norm blocker, and the engram-ordering
  (engram at 23900 BEFORE the fold at 23904 on layers {1,14}) are recorded in `design.md`.
- [x] 2.2 Metal apply (option A, DECODE path): `ds41_hc_mix` takes `il`; when
  `scale!=0 && !ffn && residual_dirs && !DS4_METAL_DISABLE_V41_RESIDUAL_STEERING` it skips
  both fused kernels (forcing the slow path) and projects `g->x` between the weighted-sum
  and `ds41_norm` with `ds4_gpu_directional_steering_project_tensor` (projective, matching
  msuiche). The 40x5120 directions tensor is uploaded to `ds41_gpu_graph` in
  `ds4_session_create` (freed in `ds41_graph_free`); `cpu_load_directional_steering` now
  loads the file for the Metal path too when residual is active. Off keeps the fast path
  (bitwise identical).
- [~] 2.3 PREFILL/BATCH coverage DONE: `ds41_before_attention_batch` projects `b->x` (f32,
  before the quantize) on the attention-side fold, so the prompt is steered too (verified:
  OFF bitwise identical, ON 0.5 alters output + coherent, with prefill+decode). The
  per-row prefill route goes through `ds41_hc_mix` (already steered). REMAINING: the CPU
  reference (`cpu_directional_steering_project_rows(scratch->attn_cur, dirs, il, 1, scale)`
  after ds4.c:11595, reference path only) and the token-major `ds41_decoder_prepare` fold
  (only hit for very long prompts ~24.5K+; the typical 1k-10k path is covered).
- [x] 2.4 `--dir-steering-residual F` in CLI/server/help + `ds4_engine_options` field +
  engine field/copy + the disable env (classified, env-check 503). Setting it sets
  `directional_steering_scale_set` so a file does not also default `ffn=1`. (bench has no
  steering flags; not added.)

## 3. Verify

- [x] 3.1 No-op gate: baseline vs `--dir-steering-file v41-msuiche.f32 --dir-steering-residual
  0` on a benign prompt -> BITWISE IDENTICAL completion (scale 0 keeps the fast fused path).
  `make test` EXIT=0, env-check 503.
- [ ] 3.2 Drop-in refusal-efficacy — via `402` (model-backed, user-run). Benign
  effectiveness CONFIRMED: at residual 0.5 the output changes vs baseline and stays
  coherent (the mechanism alters the stream at the knee). Still to settle with `402`:
  whether it reproduces msuiche's refusal removal (refusal32 4->24), the sign, the +1 index
  shift, and whether prefill coverage (2.3) is needed. DECODE-only today.

## 4. Docs

- [x] 4.1 `dir-steering/README.md`: the ffn/attn/residual 3-row site table + the
  `--dir-steering-residual` runtime option, that msuiche's vector is `residual_stream_post_layer`
  (wrong at ffn/attn) and that setting residual does not auto-enable ffn, plus the
  decode-only coverage note. The V4.1 refusal block stays verbatim (lifted by 400's opt-in).
- [x] 4.2 Provenance in `docs/upstream-prs.md` (msuiche GLP-39; distributedcognition
  grimjim norm-preserving biprojected abliteration), with the +1 offset finding; not in
  source comments.

## 5. Integration

- [x] 5.1 `make test` EXIT=0 (env-check 503). `openspec validate
  401-residual-steering-hook-msuiche --strict` passes. Disabled-path identity verified
  directly (baseline == `--dir-steering-residual 0`, bitwise). The full parity oracle and
  the prefill/batch + CPU coverage (2.3) remain. Standing commit authority on `sf/steering`.
