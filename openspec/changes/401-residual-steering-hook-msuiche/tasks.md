# Tasks

Depends on `400` (gate opt-in). Prerequisite for the drop-in check (3.2): the user
sets `HF_TOKEN` and accepts the Responsible Use Agreement on both repos; downloads go
to `/tmp`.

## 1. Converter

- [ ] 1.1 `dir-steering/tools/controlvector_to_f32.py`: read a GGUF `controlvector`,
  assert arch `controlvector` and 39 `direction.<N>` (fp32, 5120, unit norm), write
  `.f32` 40x5120 (L0 zeros, `direction.N`->layer N) and a `.json` sidecar (hook,
  `alpha_default`, `content_sha256`, base revision, provenance). Verify on a synthetic
  3-layer GGUF fixture that the bytes and indexing are exact (a `__main__` assert
  self-check, no framework).
- [ ] 1.2 Refuse a mismatched vector: wrong arch, wrong width, missing `direction.1`,
  or a non-unit row past a tolerance. Verify each exits naming the cause.

## 2. Residual-stream hook

- [ ] 2.1 Locate the post-HC-fold, pre-engram single-5120-stream tensor in the V4.1
  graph (decode and prefill/token-major), layers 1-39. Record the tensor and the two
  call sites in the design. Verify by reading the graph that it is the mean-reduced
  stream before the engram read on layers {1,14}.
- [ ] 2.2 Metal: bind `ds4_gpu_directional_steering_project_tensor` at that site under
  a new `residual` scale; gate allocation on a non-zero scale. Verify a graph dump
  shows the edit applied at the fold, not at `ffn_out`.
- [ ] 2.3 CPU reference: mirror with `cpu_directional_steering_project_rows` at the
  equivalent point. Verify CPU and Metal agree on a model-less fixture within
  tolerance.
- [ ] 2.4 `--dir-steering-residual F` in CLI/server/bench/help; the
  `ds4_engine_options` field; any disable env classified in `ds4_env.def`. Verify
  `make env-check` and `--help`.

## 3. Verify

- [ ] 3.1 No-op gate: `--dir-steering-residual 0` (and no file) bitwise identical.
  Verify `make test-deepseek41-decode-switch SWITCH=<the residual disable env>`.
- [ ] 3.2 Drop-in (needs the gated vector): convert msuiche's GGUF, run
  `--allow-v41-steering --dir-steering-file msuiche.f32 --dir-steering-residual 0.5`
  on 5-10 prompts the base refuses. Verify the base refuses and the steered run
  answers; read the completions, not only a keyword. Record which site/tensor was
  confirmed. Harness A/B is not used here (no speed claim); the model run is a single
  manual check under the shared lock.

## 4. Docs

- [ ] 4.1 `dir-steering/README.md`: the site table (ffn/attn/residual), which vector
  uses which hook, and that a residual-hook vector applied at ffn is wrong. Keep the
  V4.1 refusal block verbatim (now lifted by `400`'s opt-in). Verify no doc claims the
  ffn hook serves msuiche's vector.
- [ ] 4.2 Provenance in `docs/upstream-prs.md`/registry (msuiche GLP-39, grimjim
  method): not in source comments.

## 5. Integration

- [ ] 5.1 `make test` (incl. env-check), parity on the disabled path token-identical,
  `openspec validate 401-residual-steering-hook-msuiche --strict`. No commit or push
  without a request.
