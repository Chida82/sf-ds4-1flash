# Tasks

Conditional on an acceptance on the 44-id set (`com-steering/kpi.md`) naming a
winning configuration over the `msuiche` single-source baseline, with the quality
guards preserved. Resolved positively 2026-10-23 (`candor`). No commit, push or
archive without a separate explicit request.

## 1. Selection from a measured acceptance

- [x] 1.1 Read the identified acceptance runs and extract the winning
  configuration's slot vectors, hashes, scales, phase gates and scores. Done
  2026-10-23: `com-steering/result.md` rows `equi-7-44` 41.6 `C41 D2 R1 /44`
  (nothink) and `equi-7+q1-7think-44` 39.0 `C39 D0 R5 /44` (think); verdict runs
  (`/44`), not screens; baseline `msuiche-1017@7` 26.7 beaten in nothink.
- [x] 1.2 Record the selection as data in a provenance record. Done 2026-10-23:
  `com-steering/profiles/sf-ds4-1flash-candor.json` (slots, hashes, scales,
  phases, accepting run ids, baseline, decider note). A later acceptance
  re-records rather than editing in place; the 2026-10-16 non-adoption stays
  readable in `design.md`.

## 2. Bundle and name the default

- [x] 2.1 Bundle the chosen configuration with a provenance sidecar and write the
  three missing slot-parent vector sidecars. Done 2026-10-23: profile
  `com-steering/profiles/sf-ds4-1flash-candor.sfsteer` (self-contained, matrix
  hashes verified by `make_profile.py --show`, exit 0) + sidecars
  `com-steering/vectors/v41-mrfk-q0.json`, `v41-mrfk-q1.json`,
  `v41-dwarfstar-wo.json`. Sidecar hashes match the bundled bytes.
- [x] 2.2 Name the recommended profile and how it is passed in the docs. Done
  2026-10-23: `com-steering/README.md` (recommended-default line + provenance
  pointer) and the child `AGENTS.md` steering line. The docs state steering stays
  opt-in and the default applies only when passed. `download.sh` is unchanged: the
  profile and vectors ship in-repo, not as Hugging Face components.

## 3. Preserve the off path and the gate

- [x] 3.1 A run without the steering opt-in still refuses steering exactly as
  before. Verified by construction: no engine/kernel/frontend code changed (only
  `.json`/`.md`), so the `400` admission path is untouched.
- [x] 3.2 The disabled-steering inference path and the parity gate are unchanged.
  Verified by construction: no `ds4*.c`/`.m`/`.metal` change; steering-off is
  bitwise as before.

## 4. Conditional adoption

- [x] 4.1 Superseded 2026-10-23 by adoption (§Decision recorded 2026-10-23 in
  `design.md`): `candor` beats `msuiche` on the 44-id set, so a default ships.
  History: on 2026-10-16 no candidate beat `msuiche` and non-adoption was
  recorded; that block is kept readable, not deleted.

## 5. Integration

- [x] 5.1 Done 2026-10-23: `openspec validate 406-derived-direction-default
  --strict` is valid (exit 0); the four sidecars parse as JSON; profile matrix
  hashes verified by `make_profile.py --show` (exit 0) and match the sidecars.
  The full `make test` model-less suite was run and is green (every named test
  PASS/OK through the last target); expected, since the diff is `.json`/`.md` only
  and touches no `.c`/`.m`/`.metal`/frontend code.

## Workflow follow-up

- Commit, push and archive require a separate explicit request.
- A new accepted candidate re-runs this selection; it does not fork the change.
- `420` re-runs after this lands (it bundles a default).
