# Proposal

## Why

V4.1 needs an explicitly defined steering intervention whose effect does not silently depend on the prefill route or cached state. The existing fold edit is a useful experimental baseline, but it is not the published mean-residual, pre-Engram intervention and has not established full behavioral efficacy.

## What Changes

- Define `--dir-steering-residual F` as a projective edit of the **weighted attention-input HC fold**, after Engram on layers that use it, before attention normalization. Keep the existing direct layer mapping as the baseline, not as a proven source-hook correspondence.
- Check whether decode, batch prefill and decoder-key reconstruction place the fold rounding on different sides of the projection. If a route-agreement test shows a difference beyond FP32 tolerance, align them to one order and bump the intervention revision; otherwise record the agreement and change nothing. The unsteered path is preserved exactly either way, and no recorded evidence is invalidated by assertion.
- Finish missing `ds41_decoder_prepare` coverage, including ordinary wide sweeps around 3-4K tokens, and provide an isolated CPU reference for the edit without enabling full CPU V4.1 inference.
- Harden conversion and runtime input validation; distinguish source-hook metadata from actual application-hook metadata. Preserve one raw 40x5120 f32 matrix and zero rows for masked layers.
- **BREAKING diagnostic correction:** keep legacy FFN/attention flags and `/steer`, but reject unsupported active V4.1 uses instead of reporting success without an edit. CLI/server are the steering frontends; no bare bench flag.
- Refuse active steering together with persistent KV reuse and snapshot save/load until a steering identity exists; existing caches are never touched. The identity descriptor is deferred to the change that first needs steered persistent state.
- Establish state-level no-op controls, enabled-path coverage tests and measured enabled overhead. Behavioral acceptance uses `402`; alternative HC sites belong to `405`.

## Capabilities

### New Capabilities
- `directional-steering`: additional contracts for the capability introduced by in-flight `400`: the weighted-fold intervention, vector validation, unsupported-site diagnostics and the steering/persistent-state guard. These are ADDED requirements; no durable main spec exists yet.

### Modified Capabilities
None in the current main-spec inventory.

## Impact

- `ds4.c`, `ds4.h`: V4.1 graph paths, engine validation, isolated reference and the steering/persistent-state guard.
- `ds4_cli.c`, `ds4_server.c`, `ds4_help.c`: accurate site/error descriptions.
- `ds4_kvstore.c/.h`: untouched; the guard rejects the combination before any cache access.
- `ds4_metal.m` and existing Metal kernels only if a test proves a wrapper change necessary; reuse the projection kernel first.
- `dir-steering/tools/controlvector_to_f32.py`, graph/kernel tests, Makefile test wiring, env classification and relevant docs.
- Depends on `400`. Correctness tests do not wait for the complete `402` benchmark; `402` can be integrated in parallel. No schedule, fused vector or published-efficacy replication is required to finish this runtime change.
