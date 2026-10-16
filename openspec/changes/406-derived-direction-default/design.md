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
disabled-steering path, deriving or fusing vectors here (that is `404`/`405`),
adding an engine/kernel knob, or shipping a rank greater than one.

## Decisions

### D1. Selection is data from a run, not a hand-pick

The default is recorded from one identified `402` acceptance summary: the winning
candidate's vector hash, `402` run id, scale, source/application identity and the
guard results it passed. A file promoted without an accepting run is rejected.
Re-selection on a later win re-records from that run; it does not edit the old
selection in place, so the superseded provenance stays traceable.

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

If no `404`/`405` candidate beats `msuiche`-alone through `402` with the guards
preserved, no default is shipped, `msuiche` stays the named reference, and the
negative result is recorded. A later better candidate re-runs this selection.

## Risks / Trade-offs

- [A default implies auto-steering] -> docs and tests state the opt-in refusal is
  unchanged and the default is applied only when passed.
- [Provenance drifts from the shipped bytes] -> the sidecar records the vector hash
  and accepting run id; a mismatch invalidates the default.
- [Selecting before `402` is trustworthy] -> selection consumes an identified
  acceptance summary, not a screen or a few clean answers.

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
