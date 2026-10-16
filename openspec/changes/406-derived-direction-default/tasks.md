# Tasks

Conditional on a `402` acceptance naming a winning `404`/`405` candidate over the
`msuiche` single-source baseline, with the quality guards preserved. No commit,
push or archive without a separate explicit request.

## 1. Selection from a measured acceptance

- [ ] 1.1 Read one identified `402` acceptance summary and extract the winning
  candidate's vector hash, scale, source/application identity and guard results.
  Verify the summary is an acceptance (eligible verdict, controls passed), not a
  screen or a report-only first pass; a hand-picked file without such a run is
  refused.
- [ ] 1.2 Record the selection as data (candidate id, `402` run id, scale, vector
  hash) in a small provenance record. Verify a later acceptance re-records rather
  than editing the old selection in place, and the superseded provenance stays
  readable.

## 2. Bundle and name the default

- [ ] 2.1 Bundle the chosen direction with a provenance sidecar (source, derivation
  or fusion method, accepting `402` run id, scale), reusing the `401`/`404` sidecar
  shape. Verify the sidecar's vector hash matches the bundled bytes.
- [ ] 2.2 Name the recommended vector and scale in `download.sh` and
  `dir-steering/README.md`/`docs/REFUSAL_VALIDATION.md`. Verify the docs state that
  steering stays opt-in and the default is applied only when passed explicitly.

## 3. Preserve the off path and the gate

- [ ] 3.1 Verify a run without the steering opt-in still refuses steering exactly
  as before the default was bundled (reuse the `400` admission test).
- [ ] 3.2 Verify the disabled-steering inference path and the parity gate are
  unchanged (no engine/kernel change; steering off is bitwise as before).

## 4. Conditional adoption

- [x] 4.1 If no candidate wins through `402`, ship no default, keep `msuiche` named
  as the reference, and record the negative result. Verify nothing is bundled and
  the docs do not claim an accepted default. Done 2026-10-16: recorded in
  `design.md` ("Decision recorded"); no candidate beats msuiche@5 on breadth, no
  `eligible: True` run exists (margins never set), nothing bundled, `download.sh`
  and docs name no default. msuiche@5 reference, fused@7 quality alternative.

## 5. Integration

- [ ] 5.1 Run the model-less checks and `openspec validate 406-derived-direction-default --strict`.
  Verify the selection/provenance records and docs match the accepting run, and
  that `402`/`404`/`405` are not marked implemented by this change.

## Workflow follow-up

- Commit, push and archive require a separate explicit request.
- A new accepted candidate re-runs this selection; it does not fork the change.
- `420` re-runs after this lands if it bundles a default.
