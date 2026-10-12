# Tasks

Depends on `400` (gate opt-in). Prerequisite for the drop-in check (3.2): the user
sets `HF_TOKEN` and accepts the Responsible Use Agreement on both repos; downloads go
to `/tmp`.

Status 2026-10-13: Group 1 (converter) DONE and confirmed on the real msuiche GGUF.
Group 2 investigation (2.1) DONE and written into `design.md` ("Investigation findings").
It surfaced that the hook is a WIDE, DELICATE change to the active `ds41_*` hot graph
path (force the slow `ds41_hc_mix` path, thread `il`, upload a new directions tensor,
mirror on prefill/batch, CPU reference) AND a real architectural choice (option A vs B:
the fold `g->x` is post-engram on layers {1,14} and fused with the rms-norm). Per the
repo's "stop and ask on `ds4.c` hot-path ambiguity" rule, the apply (2.2-2.4, 3.x) is
HELD for the owner's A/B go-ahead rather than landed blind overnight. The frontend flag
plumbing was drafted and reverted (kept clean); the exact edits are in `design.md`'s plan.

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
- [ ] 2.2 Metal apply — HELD for the A/B decision (see `design.md`). Plan A: force the
  slow `ds41_hc_mix` path when `scale!=0 && !ffn` and project `g->x` between the
  weighted-sum (23600) and the norm (23601) with `ds4_gpu_directional_steering_project_tensor`;
  upload the directions tensor in `ds41_graph_alloc`. Not landed blind.
- [ ] 2.3 CPU reference — HELD with 2.2: `cpu_directional_steering_project_rows(scratch->attn_cur,
  dirs, il, 1, scale)` after the fold (ds4.c:11595). CPU has no engram, so no ordering issue.
- [ ] 2.4 `--dir-steering-residual F` in CLI/server/help + the `ds4_engine_options` field
  + the disable env — drafted, reverted; HELD with 2.2 so no flag lands that silently
  no-ops on Metal. (bench has no steering flags; not added.)

## 3. Verify

- [ ] 3.1 No-op gate — HELD with the apply: scale 0 keeps the fast fused path, bitwise
  identical. The real proof is a baseline vs `--dir-steering-residual 0` decode compare.
- [ ] 3.2 Drop-in — HELD with the apply. The converted vector `v41-msuiche.f32` is READY;
  the run settles site/index/sign (404's +1 offset is the index hint) and whether A
  reproduces msuiche's removal (refusal32 4->24). Manual, single run under the lock.

## 4. Docs

- [~] 4.1 `dir-steering/README.md` now has the V4.1 control-vector + fusion workflow and
  that msuiche's vector is `residual_stream_post_layer`, WRONG at ffn/attn (added with
  404). The formal ffn/attn/residual 3-row site table lands with the `--dir-steering-residual`
  flag (2.4). The V4.1 refusal block stays verbatim (lifted by 400's opt-in).
- [x] 4.2 Provenance in `docs/upstream-prs.md` (msuiche GLP-39; distributedcognition
  grimjim norm-preserving biprojected abliteration), with the +1 offset finding; not in
  source comments.

## 5. Integration

- [ ] 5.1 HELD with the apply: `make test` (incl. env-check) + parity on the disabled
  path once 2.2-2.4 land. `openspec validate 401-residual-steering-hook-msuiche --strict`
  passes now (the converter + design + tasks are valid). Standing commit authority on
  `sf/steering` for this steering work.
