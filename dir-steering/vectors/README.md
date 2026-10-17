# dir-steering/vectors — reference steering vectors (tracked)

Durable, version-controlled home for the refusal-direction vectors we compare in
analysis. `dir-steering/out/` is the regenerable working dir (gitignored): tools
emit candidates there and `eval/` reads from there. This directory is the
archive — the reference vectors worth keeping for future analysis, each with
provenance.

Format: little-endian float32, row-major `[layer][embd]`, 40 × 5120 = 819200 B.
Projective directions (no inherent sign); ds4 removes the direction with a
positive `--dir-steering-residual` scale. Layer 0 is masked to zero (msuiche
convention), so 39 layers are active.

## Vectors

| file | origin | provenance |
|---|---|---|
| `v41-msuiche.f32` | 402 | refusal direction from msuiche activation diffs (`dom_per_layer`); base `deepseek-ai/DeepSeek-V4.1-Flash` rev `fb2764a5`. Sidecar `v41-msuiche.json`. |
| `v41-abliteration-attn.f32` | 408 | direction recovered from audreyt's weight-diff (left singular vector of ΔW at `attn_output_b`), sign-aligned to msuiche; rank-1 share 0.89–0.92; \|cos\| median 0.72 to msuiche (early ~0.2 → mid-late ~0.82). |
| `v41-fused-msuiche-audreyt-denoise.f32` | 408/404 | `unit(msuiche + audreyt)` per layer (offset 0), the denoise fusion of the two reference directions above. Candidate for a 402 axis-A comparison. Sidecar `…-denoise.json` carries the per-layer cosines. |
| `v41-dealignai-wo.f32` | 409 | dealignai FP8 weight diff (base `deepseek-ai/DeepSeek-V4.1-Flash`, edited `dealignai/DeepSeek-V4.1-Flash-UNCENSORED-FP8`): left singular vector of ΔW at `wo_b`, layers 10–36 nonzero, rank-1 share 0.80–0.96; \|cos\| median 0.22 to msuiche, 0.21 to audreyt; recovery `ec1b5c3`, `docs/steering-measurements.md` block 2026-10-16. Attention-write direction, live at the attention-input fold. |
| `v41-dealignai-sharedw2.f32` | 409 | same base and checkpoint: left singular vector of ΔW at `ffn.shared_experts.w2`, layers 10–36 nonzero, rank-1 share 0.74–0.96; \|cos\| median 0.03 to `v41-dealignai-wo.f32`, ~-0.2 to msuiche/audreyt/fused, residual 0.88 against all four; `docs/steering-measurements.md` block 2026-10-17. Writes at the end of the layer, so inert at the fold; for the MoE residual-write site (409 Arm 5). |

sha256:

- `v41-msuiche.f32` — `e531274260c4da938770fa5f53eec8b9c6c814c8099e21552a298473a0c99109`
- `v41-abliteration-attn.f32` — `a0cd959c0fdcc074ad28d962c3faeeacb02d8b5039ed2c0f842a8bb99e2b86c2`
- `v41-fused-msuiche-audreyt-denoise.f32` — `e17b41ce4f33d20b7100ce7c4a66bb2596139b23868f130659d7db4555dd49f6`
- `v41-dealignai-wo.f32` — `a5a0278218798c7f6966e0497762f92837c3eb8b3011682acc4215fe5e2e5279`
- `v41-dealignai-sharedw2.f32` — `799452aa1bd66c5e1299d003ae916ce8e65c0019e97cc3dfbd68480d16318d75`

`v41-msuiche.f32` is a snapshot of the live working copy under `dir-steering/out/`
(same bytes); the out/ copy is what the Makefile and `eval/` reference.

Regenerate the fusion (pure Python, no model):

```sh
python3 dir-steering/tools/fuse_directions.py \
  --msuiche dir-steering/vectors/v41-msuiche.f32 \
  --f32-b audreyt:dir-steering/vectors/v41-abliteration-attn.f32 \
  --tag=-msuiche-audreyt --out dir-steering/vectors
```
