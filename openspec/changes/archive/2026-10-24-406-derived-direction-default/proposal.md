# Proposal

## Why

The steering investigation produced a composed direction that beats the
single-source `msuiche` baseline on the full acceptance set without an engine
change. Until this change the winner stayed an experiment artifact: the vectors
under `dir-steering/out/`, the shipped profile under `com-steering/profiles/`,
and no provenance pinning the shipped bytes to the run that chose them. An
operator had to rediscover which profile and scale to pass. This change bundles
the chosen configuration as the child's recommended default steering profile with
provenance, and names it in the docs. It is **conditional** and resolves
**positively**: a candidate won, so a default ships; the 2026-10-16 non-adoption
record is superseded, not deleted.

## What Changes

- Record the pinned selection from the identified acceptance runs in
  `com-steering/result.md`: the winning configuration's slot vectors and hashes,
  scales, phase gates and the accepting run ids. Selection is data from a run,
  never a hand-picked file.
- Ship the chosen configuration as the recommended default steering **profile**
  (`sf-ds4-1flash-candor`, a `.sfsteer` bundling two near-orthogonal slots) with a
  provenance sidecar (slots, hashes, accepting runs, scales, decider note), and
  write the three missing vector sidecars its slots rest on (`v41-mrfk-q0`,
  `v41-mrfk-q1`, `v41-dwarfstar-wo`). Name the profile as the one to pass in the
  docs. Steering stays **opt-in and refused by default** (`400`/`401`); "default"
  means the recommended bundled profile, never an auto-applied edit.
- Keep the disabled-steering inference path and the parity gate unchanged: this
  change adds no engine or kernel code and does not alter the off path.
- **Conditional adoption, resolved positively.** The win is measured on the
  44-id acceptance set (`com-steering/kpi.md`), recorded in `com-steering/result.md`.
  A later configuration that beats it re-runs this selection rather than forking it.

## Capabilities

### New Capabilities
- `steering-vectors`: measurement-gated selection of a shipped default
  configuration, with provenance tracing the shipped bytes to the acceptance runs
  that chose them.

### Modified Capabilities
None.

## Impact

- `com-steering/` provenance (three vector sidecars + the profile selection
  sidecar), `com-steering/README.md` and the child `AGENTS.md` naming the
  recommended default profile and how it is passed.
- `download.sh` is **not** changed: the profile and its vectors ship in-repo, not
  as Hugging Face components, so there is nothing to download.
- Depends on `417` for the profile mechanism and on the composed candidate
  (`q0dwarf-equi` + `mrfk-q1`); not on `402` (archived, acceptance margins never
  set) nor on `404`/`405`. No production engine/kernel change, no change to the
  opt-in refusal or the disabled-steering path, no new global dependency.
- A shipped default never weakens the controls or the launch policy, and never
  turns steering on by default. Benign / over-refusal of the shipped directions is
  recorded as an open validation, not a claimed result.
