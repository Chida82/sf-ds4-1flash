# Proposal

## Why

`404` fuses the two external V4.1 directions and `405` derives one at the actual
runtime site from controlled contrast pairs; `402` scores any candidate. None of
these ships a default: the best vector stays an experiment artifact under
`dir-steering/out/`. If a candidate beats the single-source `msuiche` baseline on
the full `402` acceptance without worsening the quality guards, the child should
bundle it as the recommended default steering vector with provenance, so an
operator does not have to rediscover which file and scale to pass. This change is
**conditional**: it ships a default only on that measured win, and records
non-adoption otherwise.

## What Changes

- Record a single pinned selection from an identified `402` acceptance run: the
  winning candidate's vector hash, source/application identity, scale and the
  report it was accepted under. Selection is data from a run, never a hand-picked
  file.
- Bundle the chosen direction as the child's recommended default steering vector
  with a provenance sidecar (source, derivation or fusion method, `402` run id,
  scale), and name it in `download.sh`/docs as the vector to pass. Steering stays
  **opt-in and refused by default** (`400`/`401`); "default" means the recommended
  bundled candidate, never an auto-applied edit.
- Keep the disabled-steering inference path and the parity gate unchanged: this
  change adds no engine or kernel code and does not alter the off path.
- **Conditional adoption.** If no `404`/`405` candidate beats `msuiche`-alone
  through `402` with the guards preserved, ship no default, keep `msuiche` as the
  named reference, and record the negative result. A later better candidate
  re-runs this selection rather than forking it.

## Capabilities

### New Capabilities
- `steering-vectors`: measurement-gated selection of a shipped default direction,
  with provenance tracing a candidate to the `402` acceptance run that chose it.

### Modified Capabilities
None.

## Impact

- `dir-steering/out/` provenance of the bundled candidate, `download.sh` and
  `dir-steering/README.md`/`docs/REFUSAL_VALIDATION.md` naming the recommended
  vector and scale.
- Depends on `402` for acceptance and on `404`/`405` for candidates; no dependency
  on `403`. No production engine/kernel change, no change to the opt-in refusal or
  the disabled-steering path, no new global dependency.
- A shipped default never weakens `402`'s controls or launch policy, and never
  turns steering on by default.
