# Proposal

## Why

The V4.1 control vectors are applied at a specific site. msuiche's card is explicit:
the hook is `residual_stream_post_layer` — on this architecture (hc_mult=4) the
post-layer hyper-connection fold reduced to a single 5120 stream by the mean over
the four hc copies, taken pre-engram, derived and applied there. "A reader that
applies only [the `ffn_out_pre_residual`] hook must refuse this file." ds4's existing
steering hooks are `ffn_out` (pre-residual) and `attn_out` — the wrong site for these
vectors. To use msuiche's (and any `residual_stream_post_layer`) vector, V4.1 needs a
steering application point at the post-HC-fold, pre-engram, single-stream residual,
plus a converter from the GGUF `controlvector` to the `.f32` the runtime loads.

## What Changes

- **Residual-stream hook.** A steering application point at the post-HC-fold (mean
  over the 4 hc copies), pre-engram, single 5120 stream, in the V4.1 graph (Metal)
  and the CPU reference. `--dir-steering-residual F` (default 0), applied as
  `y -= F * d[L] * dot(d[L], y)` at that site. The existing `--dir-steering-ffn/-attn`
  are unchanged, for `ffn_out_pre_residual`-style vectors.
- **Converter.** `dir-steering/tools/controlvector_to_f32.py`: reads a GGUF
  `controlvector` (39 `direction.<N>`, fp32, 5120, unit norm), writes ds4 `.f32`
  40x5120 (layer 0 zeros; `direction.N` -> layer N, no offset) and a `.json` sidecar
  (hook=`residual_stream_post_layer`, `alpha_default`, `content_sha256`, base
  revision, provenance).
- **msuiche drop-in.** Load the converted vector at `--dir-steering-residual 0.5`
  (= msuiche alpha; ds4 positive scale removes the direction, matching
  `h -= alpha*(h.d)d`). The non-monotone alpha and the L1-6 null-gate caveat are
  carried in the sidecar and the docs.
- **No-op gate.** Scale 0 / no file -> no tensor allocated -> bitwise identical.

## Capabilities

### Modified Capabilities
- `directional-steering`: adds the `residual_stream_post_layer` application point for
  V4.1 and the control-vector converter; the existing ffn/attn points are unchanged.

## Impact

- `ds4.c`: the CPU reference projection at the fold site; the V4.1 graph wiring that
  passes the residual-steering scale.
- `ds4_metal.m` / `metal/`: the Metal projection at the post-HC-fold tensor (reuse
  `ds4_gpu_directional_steering_project_tensor`; no new kernel if the fold tensor is
  addressable).
- `ds4_cli.c`, `ds4_server.c`, `ds4_bench.c`, `ds4_help.c`: `--dir-steering-residual`.
- `ds4_env.def`: any new disable env for the site.
- `dir-steering/tools/controlvector_to_f32.py` (new), `dir-steering/README.md` (the
  site table).
- `docs/upstream-prs.md` / registry: provenance (msuiche GLP-39, grimjim method); not
  in source comments.
- Depends on `400` (the gate opt-in).
