# Proposal

## Why

Change 419 landed the two-stage additive closure channel and chose `close2` as the
configuration that breaks the think reasoning-loop without touching compliance, but it
left the channel out of the shipped default `sf-ds4-1flash-candor`: a caller who passes
`--steering-profile sf-ds4-1flash-candor` still gets the loop-prone 418-C profile and has
to know to pass `close2` instead. The evidence to fold the channel into the default is
already in hand and is strongly favourable, so the default should carry it.

## What Changes

- Rebuild the shipped `sf-ds4-1flash-candor.sfsteer` to carry its existing slots (equi
  scale 7 both, q1 scale 7 think, 418-C decay) **plus** the `close2` closure object
  (satisfied-closure vector, scale 0.4 from onset 2700..3100, ramp 256; scale2 0.9 from
  onset+2000 over 512; think only). The profile's internal name stays
  `sf-ds4-1flash-candor`.
- Update the pin `com-steering/profiles/sf-ds4-1flash-candor.json` to the new slot/closure
  hashes, scales, phases, schedule and accepting run ids.
- Update the docs that quote the old numbers (`com-steering/README.md`,
  `com-steering/result.md` / `kpi.md`, and the `AGENTS.md` identity note if it quotes a
  think figure) to the promoted profile's: non-think unchanged, think 39.0 → 41.0, loop
  13/44 → 3/44.
- **Not changed**: non-think behaviour (the closure channel is inert outside think, and
  the 419 non-think guard is byte-identical), the fold slots, the engine, and the
  tooling. The named alternatives `close0.25` / `close0.5` / `close2` stay as they are.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `directional-steering`: the "Shipped candor schedule (418-C)" requirement changes —
  the shipped candor profile now also carries the two-stage closure channel, so it must
  break the think reasoning-loop (loop 3/44 on the fixed 44 at MT=12000) while keeping the
  non-think output byte-identical to the pre-promotion candor.

## Impact

- `com-steering/profiles/sf-ds4-1flash-candor.sfsteer` (rebuilt, same internal name),
  `com-steering/profiles/sf-ds4-1flash-candor.json` (re-pinned).
- Docs: `com-steering/README.md`, `com-steering/result.md`, `com-steering/kpi.md`,
  `AGENTS.md` (identity note, only if it quotes a think figure).
- Spec: `directional-steering` "Shipped candor schedule" requirement.
- Runtime behaviour: callers of the default `--steering-profile sf-ds4-1flash-candor` get
  loop-breaking in think; non-think and the answer phase are unchanged. The think-level
  still comes from the frontend (unknown = 75), which sets the closure onset.
- No engine, Makefile or binary change; no new dependency.
