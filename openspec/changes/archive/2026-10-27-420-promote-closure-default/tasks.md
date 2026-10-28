# Tasks

## 1. Rebuild the shipped profile

- [x] 1.1 Rebuild `com-steering/profiles/sf-ds4-1flash-candor.sfsteer` with `make_profile.py`:
  the current candor slots (`v41-q0dwarf-equi` 7 both with `--decay 256 3.5 --decay-hold 25
  --decay-final-answer 4.0`, `v41-mrfk-q1` 7 think) plus `--closure
  v41-closure-satisfied.f32 0.4 2700 3100 256 --closure2 0.9 2000 512`, `--name
  sf-ds4-1flash-candor`
- [x] 1.2 Verify the rebuilt file against `close2`: the three embedded matrices (equi, q1,
  closure-satisfied) and the `closure` schedule object are byte/field-identical to
  `sf-ds4-1flash-candor-close2.sfsteer`; only the header `name`/`description` differ. This
  is the promotion's identity check — no GPU run is needed because the bytes are the ones
  419 already measured
- [x] 1.3 `make test` green (profile parser and `env-check` unaffected; model-less)

## 2. Re-pin and document

- [x] 2.1 Regenerate `com-steering/profiles/sf-ds4-1flash-candor.json` from the rebuilt
  file: slot and closure SHA-256, scales, phases, the 418-C schedule and the closure
  schedule, and the accepting run ids (the 419 close2 runs: think `20261027-100817`/
  `-104301`/`-112047`/`-140001`, non-think guard `20261027-043026`, benign gate
  `level-75-close2`)
- [x] 2.2 Update the docs that quote the old think number to the promoted profile's
  (non-think unchanged, think 39.0 → 41.0, loop 13/44 → 3/44): `com-steering/README.md`
  (candor section), `com-steering/result.md` / `com-steering/kpi.md`, and the `AGENTS.md`
  identity note only if it states a think figure
- [x] 2.3 Note in `com-steering/result.md` that the shipped candor now carries the closure
  channel and that `close0.25`/`close0.5`/`close2` remain as named alternatives

## 3. Validate

- [x] 3.1 `openspec validate 420-promote-closure-default` passes
- [x] 3.2 Run the StarForge parity oracle as the standard pre-PR gate (unsteered, so the
  profile swap does not move it; confirms no unrelated regression)
