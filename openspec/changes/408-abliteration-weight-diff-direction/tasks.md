# Tasks

## 0. Acquisition & preconditions
- [x] 0.1 Acquire the `audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF` `Q2` checkpoint
  (same ds4 project, same quantization as our base — highest priority source) via
  `hf download` into the shared cache; never copy a GGUF into the repo (SPEC §C). Done:
  365,713,686,528 bytes (identical size to base), in the shared HF cache.
- [x] 0.2 Confirm the base `Q2` GGUF is present; record its quant type and the tensor
  list of the residual-writing sites. Done: standard GGUF v3, 1046 tensors; residual-writing
  sites per `blk.N` are `attn_output_b` (Q8_0 `[8192,5120]`), `ffn_down_shexp` (Q8_0
  `[2304,5120]`), `ffn_down_exps` (Q2_K `[2304,5120,384]`). Reader at
  `dir-steering/tools/` (see 6.1).
- [x] 0.3 Inspect the abliterated GGUF `ggml_type` of those tensors to pick the dequant
  path (standard reader vs ds4-backed dump — design D5). Done: abliterated tensors keep the
  base `ggml_type` (edited in place, not requantized), so the standard numpy reader (D5) is
  the right path; no ds4-backed dump needed.

## 1. Comparability & edit location (D1)
- [x] 1.1 Raw quantized-byte diff of matching tensors (base vs abliterated), no dequant;
  emit the edited-tensor map. Done (`dir-steering/tools/abl_footprint.py`,
  `docs/steering-measurements.md` 2026-10-15): edited all 40 layers at `attn_output_b` (Q8_0)
  and `ffn_{gate,up,down}_exps` (Q2_K); `shexp`, attn-input, HC, norms, `token_embd`, `output`
  untouched.
- [x] 1.2 Base-match sanity check: confirm tensors the abliteration should not touch are
  byte-identical (clean per-tensor edit); if everything differs, record it as a fully
  requantized file (requant noise) and stop before publishing any direction. Done:
  `token_embd` and every other untouched Q8_0/attention tensor are byte-identical → a clean
  in-place per-tensor edit, not a requantization; proceeding is safe.

## 2. Direction recovery (D2)
- [x] 2.1 Dequantize only the edited residual-writing tensors. Done for the clean Q8_0 site
  (`attn_output_b`). The other edited residual-writing site, `ffn_down_exps`, is Q2_K and is
  left as footprint only: abliteration vs quant noise is not separable in Q2_K without the base
  BF16, and the Q8_0 site already gives a clean recovery.
- [x] 2.2 SVD of `ΔW` per layer; emit a per-layer unit-norm f32 direction in the existing
  format; record each layer's leading singular-value share; flag non-rank-one layers as
  low-confidence. Done: leading singular-value share 0.89–0.92 across all 40 layers (no
  low-confidence layer); candidate `dir-steering/vectors/v41-abliteration-attn.f32` (40×5120).
- [x] 2.3 Fix the SVD sign against the `402` reference; record the convention. Done: each
  layer's recovered row is flipped to `cos(r, v402_layer) ≥ 0` before emission.

## 3. Geometry report (D3)
- [x] 3.1 Per-layer cosine to the `402` msuiche vector on the common layer mask; report
  the edited-layer map and the recovered rank. Done: |cos| median 0.72, min 0.12 (early) to
  max 0.82 (mid-late), n=39 (layer 0 masked in 402); rank ≈ 1 per layer (share 0.89–0.92).
- [x] 3.2 Diagnose a single global `r` (mutual per-layer cosine of the recovered rows). Done:
  mutual |cos| median 0.16 (max 0.95 adjacent) → per-layer, slowly-rotating, not one global `r`
  — matches the 402 geometry (`14ea4d6`).
- [x] 3.3 Record the geometry finding in `docs/steering-measurements.md` as evidence of
  what the abliteration targeted, not as efficacy. Done (2026-10-15 block).

## 4. Evaluation (user-run — D6)
- [ ] 4.1 (user-run) axis-A at a finishing token cap vs the msuiche baseline; record as a
  completed comparison, negative results included. Candidate ready:
  `dir-steering/vectors/v41-abliteration-attn.f32`.
- [ ] 4.2 Record the outcome; adopt no runtime default in this change (defer any adoption
  or fusion to `406`/`404`).

## 5. Secondary sources
- [ ] 5.1 `distributedcognition/...-abliterated`: acquire and run the comparability check;
  if comparable, recover the direction and report its geometry against the audreyt one.
- [ ] 5.2 `drowzeys/...-Cybersecurity-Unleashed`: survey the edited-site map and its
  geometry against the general recovered direction — analysis only, no adoption.
  Site-map + mechanism survey done (`docs/steering-measurements.md` 2026-10-15, metadata only, no
  model download): publishes only `attn.wo_b` (= `attn_output_b`) layers 10–35 in FP8; rank-1
  (`k=1`, 5120-d) projective edit, `lambda_attn 3.5`, rel_fro ~5% — concurs with audreyt + msuiche on
  site/rank/layer-band. Remaining (the vector-cosine to 402): not obtainable from public artifacts
  (direction unpublished; base is a private TR3-Hybrid FP8, so a diff vs our Q2/Q8_0 is invalid; FP8
  null-space recovery swamped, ~12.5% quant error > ~5% edit). Clean route = diff vs the official
  stock FP8 `wo_b` (targeted FP8-shard download); deferred.

## 6. Tooling
- [x] 6.1 Offline weight-diff/SVD tool under `dir-steering/tools/`, run from a disposable
  `/tmp` venv (host environment untouched, SPEC §System integrity); standard-quant reader
  first, ds4-backed dequant dump as the fallback for a custom `Q2`. Done:
  `dir-steering/tools/weight_diff_direction.py` (standard GGUF reader + Q8_0 dequant + power-
  iteration SVD + 402 geometry + base-match sanity; `--selfcheck` passes) and
  `dir-steering/tools/abl_footprint.py` (edit-scope byte map). Standard reader sufficed; the
  ds4-backed fallback was not needed (0.3).
