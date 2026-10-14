# Tasks

## 0. Acquisition & preconditions
- [ ] 0.1 Acquire the `audreyt/DeepSeek-V4.1-Flash-Abliterated-GGUF` `Q2` checkpoint
  (same ds4 project, same quantization as our base — highest priority source) via
  `hf download` into the shared cache; never copy a GGUF into the repo (SPEC §C).
- [ ] 0.2 Confirm the base `Q2` GGUF is present; record its quant type and the tensor
  list of the residual-writing sites (attention output proj, shared-expert down proj).
- [ ] 0.3 Inspect the abliterated GGUF `ggml_type` of those tensors to pick the dequant
  path (standard reader vs ds4-backed dump — design D5).

## 1. Comparability & edit location (D1)
- [ ] 1.1 Raw quantized-byte diff of matching tensors (base vs abliterated), no dequant;
  emit the edited-tensor map.
- [ ] 1.2 Base-match sanity check: confirm tensors the abliteration should not touch are
  byte-identical (clean per-tensor edit); if everything differs, record it as a fully
  requantized file (requant noise) and stop before publishing any direction.

## 2. Direction recovery (D2)
- [ ] 2.1 Dequantize only the edited residual-writing tensors.
- [ ] 2.2 SVD of `ΔW` per layer; emit a per-layer unit-norm f32 direction in the existing
  format; record each layer's leading singular-value share; flag non-rank-one layers as
  low-confidence.
- [ ] 2.3 Fix the SVD sign against the `402` reference; record the convention.

## 3. Geometry report (D3)
- [ ] 3.1 Per-layer cosine to the `402` msuiche vector on the common layer mask; report
  the edited-layer map and the recovered rank.
- [ ] 3.2 Diagnose a single global `r` (mutual per-layer cosine of the recovered rows).
- [ ] 3.3 Record the geometry finding in `docs/steering-measurements.md` as evidence of
  what the abliteration targeted, not as efficacy.

## 4. Evaluation (user-run — D6)
- [ ] 4.1 (user-run) axis-A at a finishing token cap vs the msuiche baseline; record as a
  completed comparison, negative results included.
- [ ] 4.2 Record the outcome; adopt no runtime default in this change (defer any adoption
  or fusion to `406`/`404`).

## 5. Secondary sources
- [ ] 5.1 `distributedcognition/...-abliterated`: acquire and run the comparability check;
  if comparable, recover the direction and report its geometry against the audreyt one.
- [ ] 5.2 `drowzeys/...-Cybersecurity-Unleashed`: survey the edited-site map and its
  geometry against the general recovered direction — analysis only, no adoption.

## 6. Tooling
- [ ] 6.1 Offline weight-diff/SVD tool under `dir-steering/tools/`, run from a disposable
  `/tmp` venv (host environment untouched, SPEC §System integrity); standard-quant reader
  first, ds4-backed dequant dump as the fallback for a custom `Q2`.
