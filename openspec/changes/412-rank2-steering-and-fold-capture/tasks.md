# Tasks

The runtime, capture, harness threading and extractor already exist (commits
`8daabe6`, `ac2cdca`, `f70f42c`). Items marked done name the commit that did them;
open items are the verifications and documentation this change adds. Commit, push and
archive require a separate explicit request.

## 1. Second direction runtime (done, `8daabe6`)

- [x] 1.1 `ds4_engine_options.directional_steering_file2` / `_residual2`; engine fields;
  `ds41_gpu_graph.residual_dirs2` / `residual_scale2`, freed with the graph.
- [x] 1.2 Loader refactored into `ds41_load_steering_matrix(path, n_layers)` and used for
  both directions; the second file is loaded only when `residual2 != 0`.
- [x] 1.3 Second in-place fold after the first on all three routes (`ds41_hc_mix`,
  `ds41_before_attention_batch`, decoder suffix) via `ds41_steer_attention_input2`.
- [x] 1.4 Gate: `supported` requires the opt-in for file2 as for file1; needs-file guard
  for `--dir-steering-residual-2`; persistence refusal covers either direction; server
  KV-disk guard extended. Flags parsed in `ds4_cli.c` and `ds4_server.c`.
- [x] 1.5 `make test` green including the steering-fold test; benign smoke
  (msuiche@5 + abl_perp@5) coherent.

## 2. Verification this change adds

- [ ] 2.1 Bitwise off path: `make test-deepseek41-decode-switch`-style comparison of a
  single-direction run against the same run with `--dir-steering-file-2 <f>
  --dir-steering-residual-2 0` (second file present, zero scale): logits, Engram history
  and KV identical. Record the command in `dir-steering/README.md`.
- [ ] 2.2 Orthogonal composition: a synthetic test with two per-layer orthogonal unit
  directions at `s₁ = s₂ = 1` nulls both projections (`|dot(d₁,h')|, |dot(d₂,h')| < 1e-4`),
  and the result is order-independent; with a non-orthogonal pair the order matters and
  the test asserts that it does (documenting D2, not hiding it).
- [ ] 2.3 Per-layer cosine between the two loaded directions written into the run
  identity (`eval/manifest.py` `rank2` record) and printed at engine open; verify a
  msuiche + abl_perp pair reports median |cos| < 0.05 and msuiche + abliteration reports
  ~0.72.

## 3. Fold activation capture (done, `ac2cdca`)

- [x] 3.1 `ds41_dump_fold_row`: synchronize → read row 0 of the fold input → append
  5120 f32 → `begin_commands`; wired at the three routes before the folds; token-major
  route forces the slow path when the env is set.
- [x] 3.2 `DS4_V41_DUMP_STEER_INPUT` classified `probe`, unset, in `ds4_env.def`
  (`make env-check` passes, 506 names).
- [ ] 3.3 Document the row layout (tokens × 40 layers, last 40 rows = the decision
  position at `n=1`) and the "do not set in a measured run" rule in
  `dir-steering/README.md`; verify a run with the env unset shows no `probe` line at
  engine open and a run with it set prints exactly one.

## 4. Harness and extractor (done, `f70f42c` and `8daabe6`)

- [x] 4.1 `build_cli(steer2, residual2)`, `gen(...)`, `intervention_identity(... rank2)`,
  `run.py --steer2/--residual2` with the requires-`--steer`/nonzero check; `_selfcheck`
  rank-2 arm assertion.
- [x] 4.2 `eval/extract_floor_direction.py`: classes from `A_v41-msuiche@5.json`, one
  prompt per request at `n=1`, last 40 dump rows, `unit(mean_A − mean_B)`, f32 + sidecar,
  `--self-check`, `--dry-run`.
- [ ] 4.3 Extractor sidecar gains the per-layer cosine of the produced direction against
  each loaded reference direction passed with `--ref LABEL:PATH` (repeatable), so the
  "is this new" question is answered at extraction time rather than by hand.

## 5. Documentation and integration

- [ ] 5.1 `dir-steering/README.md`: a "Second direction" section (flags, gate, D2
  wording, off-path guarantee) and a "Fold capture" section (env, layout, cost, rule);
  `AGENTS.md` Identity row already names the flags — verify it matches.
- [ ] 5.2 `openspec validate 412-rank2-steering-and-fold-capture --strict`; `make test`
  with named output; `make env-check`.
