# Proposal

## Why

`404` concluded that a scalar merge of two refusal directions can only rotate the single
removed direction, and that the useful part of a second source is its component
orthogonal to the first — which must be removed as a *separate* fold. `404` D4 and `405`
both excluded a multi-direction runtime from their scope, so it was built as an
unhomed follow-up (commit `8daabe6`): a second direction file and scale at the one live
V4.1 site, applied as a second in-place fold. In the same arc a read-only activation
dump at that site (commit `ac2cdca`) and an activation-contrast extractor
(`eval/extract_floor_direction.py`, commit `f70f42c`) were added to derive a direction
from the model's own activations at the application point, as `405` D5 asks.

The behavioural result was negative for the pair it was built for — msuiche and
abliteration interfere (`docs/steering-measurements.md`, 2026-10-16) — but the runtime
and the capture are correct, tested, gated, and reusable for any future second source
(`409` and later). Code that ships needs a contract: what the second fold computes,
when two folds equal a subspace removal, what the off path guarantees, how the capture
is bounded, and what the harness records. This change gives the existing code that
contract; it adds no new mechanism.

## What Changes

- **Second residual direction (rank-2).** `--dir-steering-file-2` and
  `--dir-steering-residual-2` (CLI and server) load a second 40×5120 unit-per-layer
  f32 direction and remove it at the V4.1 attention-input fold as a second in-place
  fold, `h -= s₂·dot(d₂,h)·d₂`, after the first, on all three routes (token-major
  decode, prefill batch, decoder suffix). Constant scale only (no `403` schedule).
  Same `--allow-v41-steering` / `DS4_ALLOW_V41_STEERING` gate and the same
  `DS4_METAL_DISABLE_V41_RESIDUAL_STEERING` disable as the first direction; the
  persistence guard (`401`) covers either direction. Zero second scale is bitwise the
  single-direction run.
- **Composition contract.** Two sequential folds remove the exact 2-D span only when
  the two directions are orthogonal per layer; otherwise they compose as sequential
  removals and the shared component is removed twice. The loader records per-layer
  cosine between the two directions in the run identity; the harness refuses to call a
  non-orthogonal pair a "rank-2 span removal".
- **Fold activation capture.** `DS4_V41_DUMP_STEER_INPUT=<path>` (classified `probe`)
  appends the pre-edit fold input of row 0, one 5120-f32 row per layer, on all three
  routes, synchronising per row and forcing the slow token-major path. It is an
  extraction tool, not a release probe: output unchanged, off path a single `getenv`,
  no allocation or dispatch when unset.
- **Harness.** `eval/run.py --steer2/--residual2` and `build_cli(steer2, residual2)`
  thread the pair into generation and into the intervention identity (`rank2`
  sub-record), so a rank-2 arm is reproducible and distinguishable from a rank-1 arm.
- **Extractor.** `eval/extract_floor_direction.py` derives `unit(mean_A − mean_B)` per
  layer from the capture at base, with a sidecar (classes, counts, raw norms, hash).

## Capabilities

### Modified Capabilities
- `directional-steering`: adds the second-direction fold, its composition contract,
  the bounded fold capture and the rank-2 run identity. The opt-in gate, the
  weighted-fold intervention of the first direction and the persistence rules are
  reused unchanged.

### New Capabilities
<!-- none -->

## Impact

- `ds4.c`/`ds4.h`: second direction fields, loader reuse, second fold at the three
  sites, gate and persistence-guard extension, capture helper (`ds41_dump_fold_row`).
- `ds4_cli.c`, `ds4_server.c`: the two flags; server KV-disk guard extended.
- `ds4_env.def`: `DS4_V41_DUMP_STEER_INPUT` (`probe`, unset).
- `eval/common.py`, `eval/generate.py`, `eval/manifest.py`, `eval/run.py`:
  `steer2`/`residual2` threading and identity.
- `eval/extract_floor_direction.py`, `dir-steering/tools/hybrid_alpha.py`,
  `eval/hybrid_phaseb.py`: tooling that consumes the capture or screens candidates.
- No change to the steering-off inference path, the parity gate, or any kernel. Depends
  on `400`/`401`; `402` scores rank-2 arms unchanged. Does not reopen `404`'s
  negative result; a future second source (`409`) consumes this contract.
