# Design

## Context

Steering is opt-in and refused by default on V4.1 (`400`/`401`). The runtime
applies one projective direction per layer from a `--dir-steering-file` at the
`v41_attn_input_weighted_fold_post_engram` site, scale from `--dir-steering-residual`.
Candidates come from `404` (fusion of the two external directions) and `405`
(derivation at the runtime site from own contrast pairs). `402` is the only
acceptance path and emits an identified summary per run. Today the best vector is
left in `dir-steering/out/` and the operator is told to pass `msuiche` or a fused
file at a scale found by screening; there is no recorded, measurement-gated
default.

## Goals / Non-Goals

**Goals:** a default direction chosen only by a `402` acceptance, bundled with
provenance that traces it to that run, and docs that name the one vector and scale
to pass. Conditional: ship nothing when no candidate wins.

**Non-Goals:** turning steering on by default, changing the opt-in refusal or the
disabled-steering path, deriving or fusing vectors here (that is the steering
investigation under `com-steering/`), adding an engine/kernel knob. Rank: the
shipped profile uses the two phase-gated slots the profile mechanism (`417`)
already provides; this change adds no new removal rank or slot to the engine.

## Decisions

### D1. Selection is data from a run, not a hand-pick

The default is recorded from the identified acceptance runs on the 44-id set
(`com-steering/kpi.md`), logged in `com-steering/result.md`: the winning
configuration's slot vectors and hashes, scales, phase gates, scores/counts and
the accepting run ids, in both reasoning phases. A file promoted without an
accepting run is rejected. Re-selection on a later win re-records from that run; it
does not edit the old selection in place, so the superseded provenance stays
traceable.

The acceptance of record is the 44-id `kpi.md` verdict, not a `402` `eligible:
True` verdict: `402` was archived with its acceptance margins never set (a user
decision), so no `402` run carries that verdict. `kpi.md`/`result.md` is the
decider the standing best lives in.

### D2. "Default" is a recommendation, never an auto-edit

Shipping a default changes documentation and a bundled artifact, not runtime
behavior: a run without the opt-in still refuses steering, and the default applies
only when the operator passes the file and scale. The disabled-steering inference
path and the parity gate are untouched; this change adds no engine or kernel code.

### D3. Provenance travels with the bytes

The bundled direction carries a sidecar (reusing the `401`/`404` sidecar shape)
naming source, derivation or fusion method, accepting `402` run id and scale.
`download.sh`/docs name the vector and scale to pass. Derived vector bytes may
stay outside git; the sidecar and the `402` run id are enough to regenerate and
re-verify.

### D4. Conditional adoption and supersession

If no candidate beats `msuiche`-alone on the 44-id acceptance set (`kpi.md`) with
the guards preserved, no default is shipped, `msuiche` stays the named reference,
and the negative result is recorded. A later better candidate re-runs this
selection. (Resolved positively on 2026-10-23: `candor` won — see above.)

## Risks / Trade-offs

- [A default implies auto-steering] -> docs and tests state the opt-in refusal is
  unchanged and the default is applied only when passed.
- [Provenance drifts from the shipped bytes] -> the sidecar records the vector hash
  and accepting run id; a mismatch invalidates the default.
- [Selecting before `402` is trustworthy] -> selection consumes an identified
  acceptance summary, not a screen or a few clean answers.

## Decision recorded (2026-10-23): adoption, `sf-ds4-1flash-candor` ships as the default

Supersedes the 2026-10-16 non-adoption below (kept readable per D1). A composed
configuration now beats the single-source `msuiche` baseline on the 44-id
acceptance set (`com-steering/kpi.md`, ledger `com-steering/result.md`):

| config | phase | score | counts |
|---|---|---|---|
| `msuiche-1017 @7` (baseline) | nothink | 26.7 | `C24 D9 R11 /44` |
| **`candor` = `q0dwarf-equi @7` both + `mrfk-q1 @7` think** | **nothink** | **41.6** | `C41 D2 R1 /44` |
| same | think | 39.0 | `C39 D0 R5 /44` |

- **Ship the profile.** `com-steering/profiles/sf-ds4-1flash-candor.sfsteer` is the
  recommended default, pinned by `com-steering/profiles/sf-ds4-1flash-candor.json`
  to the accepting runs. The three slot-parent vectors get provenance sidecars
  (`v41-mrfk-q0`, `v41-mrfk-q1`, `v41-dwarfstar-wo`).
- **`mrfk-q0 @7` is the rank-1 reference** (ties 41.6 non-think, 37.0 think):
  shipped-as-profile wins on the think phase and the near-orthogonal 2D removal.
- **Open validation.** Benign / over-refusal (XSTest) of the candor directions is
  not yet measured (only `fused@7` was XSTest-clean); recorded as open, not claimed.
- **Off path and parity unchanged.** No engine/kernel code: the change is sidecars
  and docs, so steering-off is bitwise as before and the opt-in refusal is intact.
- A later config that beats 41.6 non-think without regressing think past the ~1.0
  noise floor re-records this selection (D4); it does not edit this block.

## Decision recorded (2026-10-16): non-adoption, `msuiche` stays the named reference

The candidate search is exhausted (`docs/steering-measurements.md`, 2026-10-16 blocks;
`404` follow-up note; `405` Results). Against the single-source `msuiche@5` baseline:

| candidate | breadth (hard-32, keyword, server path) | comply quality (union[:30], judge, 2048 tok) |
|---|---|---|
| **msuiche@5** | **3/32 refuse** `{6,372,426}` | n=30 at scale 6 constant: 23/30 COMPLY, 5 DEFLECT (3-arm run) |
| fused-denoise | 28/32 refuse at scale 5 | **@7: 28/30 COMPLY, 0 DEFLECT, 0 breaks** (run `20261016-105834`); hard-32 at scale 7 not measured |
| hybrid α (rank-1 rotation) | 6/32 (α=0.1) → 21/32 (α=0.3) | not judged (screen already negative) |
| rank-2 msuiche + abl_perp / + abliteration | breadth kept / — | floor still REFUSE; 372 breaks (abl_perp) |
| floor-resist (activation-extracted) | — | floor still REFUSE |

No candidate beats `msuiche` on breadth, the primary metric of broad refusal removal;
the fused direction wins comply-quality on `union[:30]` but at the only scale where its
breadth was measured it is far worse, and its breadth at scale 7 is unmeasured. No `402`
run carries an `eligible: True` verdict for any candidate, because the predeclared
acceptance margins (402 tasks 6.5/8.2) were never set — a user decision — so 1.1 has no
acceptance summary to consume and the D4 path applies:

- **Ship no default.** Nothing is bundled; `download.sh` and the docs do not name an
  accepted default.
- **`msuiche` at scale 5 is the named reference** for broad refusal removal
  (`dir-steering/vectors/v41-msuiche.f32`, `--dir-steering-residual 5`, 29/32 hard,
  ~190/205 union at the 8-token screen); the floor `{6,372,426}` is a documented residual.
- **fused-denoise at scale 7** is recorded as the comply-quality alternative on the
  `union[:30]` distribution (`v41-fused-msuiche-audreyt-denoise.f32`, `--dir-steering-residual 7`),
  not as a default: its breadth at that scale is an open measurement.
- A later candidate, or a `402` acceptance with margins set, re-runs this selection (D4);
  it does not edit this record.

## Migration Plan

Land only after a `402` acceptance names a winner. Record the selection and
provenance, name the vector/scale in docs, and verify the off path and parity are
unchanged. With no winner, record non-adoption and keep `msuiche` as the named
reference.
