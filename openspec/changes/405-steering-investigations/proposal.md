# Proposal

## Why

Steering on V4.1 (`401`) has levers whose worth only the framework (`402`) can
settle: which layers to touch, how the dose fades, whether a second site helps. This
change is the measured-investigation bucket. Each item ships a small knob only if
`402` shows it helps on axis A without hurting B/C/D (config CI rule), or stays a
documented finding. The owner wants broad removal, so one item maps how broad the
removal already reaches across domains, and one maps where the output breaks.

## What Changes

- **Per-layer scale.** An optional per-layer scale/mask over the steering direction.
  msuiche measured the dose at 3% of the residual norm at L1 rising to 41% at L30, and
  L1-6 sit below the derivation null gate. Steer only the layers with real good-vs-bad
  separation; fewer layers touched means less collateral to B/C/D. OFF (no mask) is
  bitwise identical.
- **Event-based decay.** A guarded alternative to `403`'s fixed-token schedule: the
  edit already computes `dot(d[L], y)`, so drop the scale once the projection returns
  to the comply range — the model has passed the refusal decision. Adaptive per
  prompt. OFF is bitwise.
- **Projection log.** A read-only diagnostic env that prints `dot(d[L], y)` per layer
  per token, to see when the model enters refusal mode. Output is never changed.
- **Attention second channel** (conditional). A small residual-plus-tiny-attention
  sweep vs residual alone; kept only if `402` shows it beats residual alone, else
  dropped as a finding.
- **Generalization map** (finding). Using `402`'s per-category axis, how far a single
  broad vector's removal reaches across domains (msuiche measured a refusal32/benign32
  vector transferring to cyber32 31/32 and geopolitical 32/32).
- **Breaking-point map** (finding). The scale/decay at which the text degrades
  (code-switching, repetition) on V4.1's non-monotone response — a tuning reference.

## Capabilities

### Modified Capabilities
- `directional-steering`: adds optional per-layer scale, an event-based decay mode and
  a projection-log diagnostic; each off by default and bitwise when off.

## Impact

- `ds4.c`: the per-layer scale lookup in the steering edit, the event-decay guard, the
  projection-log env read. Each small and independently reversible.
- `ds4_cli.c`, `ds4_server.c`, `ds4_bench.c`, `ds4_help.c`: the knobs that take a flag.
- `ds4_env.def`: the new envs classified (`DS4_METAL_DISABLE_*` / `probe`).
- `dir-steering/`: the per-layer scale file format and a small helper; docs.
- `speed-bench/perf-record.md` and the registry: the generalization and breaking-point
  findings.
- Depends on `401` (the residual hook), `403` (the decay it guards); measured by `402`.
