# dir-steering/vectors — reference steering vectors (provenance record)

The reference refusal directions compared during the broad-removal investigation
once lived here. The investigation is closed and the `.f32`/`.json` files are
**not kept** — the shipped `candor` profile embeds the directions it uses, and
these reference directions are regenerable from the cited sources. This file is
the record of what they were, so they can be rebuilt if the work reopens.

Format (for any rebuild): little-endian float32, row-major `[layer][embd]`,
40 × 5120 = 819200 B. Projective directions (no inherent sign); ds4 removes the
direction with a positive profile slot scale. Layer 0 is masked to
zero (msuiche convention), so 39 layers are active. All on base
`deepseek-ai/DeepSeek-V4.1-Flash`.

| direction | origin | provenance | sha256 |
|---|---|---|---|
| `v41-msuiche` | 402 | refusal direction from msuiche activation diffs (`dom_per_layer`), base rev `fb2764a5` | `e531274260c4da938770fa5f53eec8b9c6c814c8099e21552a298473a0c99109` |
| `v41-abliteration-attn` | 408 | left singular vector of audreyt's weight-diff ΔW at `attn_output_b`, sign-aligned to msuiche; rank-1 share 0.89–0.92; \|cos\| median 0.72 to msuiche | `a0cd959c0fdcc074ad28d962c3faeeacb02d8b5039ed2c0f842a8bb99e2b86c2` |
| `v41-fused-msuiche-audreyt-denoise` | 408/404 | `unit(msuiche + audreyt)` per layer, the denoise fusion of the two above | `e17b41ce4f33d20b7100ce7c4a66bb2596139b23868f130659d7db4555dd49f6` |
| `v41-dealignai-wo` | 409 | left singular vector of ΔW at `wo_b` (edited `dealignai/DeepSeek-V4.1-Flash-UNCENSORED-FP8`), layers 10–36 nonzero, rank-1 share 0.80–0.96; \|cos\| median 0.22 to msuiche, 0.21 to audreyt. Attention-write direction, live at the attention-input fold. `docs/steering-measurements.md` 2026-10-16 | `a5a0278218798c7f6966e0497762f92837c3eb8b3011682acc4215fe5e2e5279` |
| `v41-dealignai-sharedw2` | 409 | left singular vector of ΔW at `ffn.shared_experts.w2`, layers 10–36 nonzero, rank-1 share 0.74–0.96; \|cos\| median 0.03 to `dealignai-wo`, ~-0.2 to the others. Writes at the end of the layer, so inert at the fold; for the MoE residual-write site. `docs/steering-measurements.md` 2026-10-17 | `799452aa1bd66c5e1299d003ae916ce8e65c0019e97cc3dfbd68480d16318d75` |

The fusion `denoise = unit(msuiche + audreyt)` per layer was the main candidate
these fed; the method and the geometry of combining directions are in
[`../README.md`](../README.md). None of these beat the `mrfk`/`dwarfstar` pair
the shipped profile uses (`com-steering/README.md`).
