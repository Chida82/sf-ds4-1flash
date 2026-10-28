# Tasks

Depends on `401`'s vector/application contract and `402` for measured selection; no dependency on `403`. The original tool ran on real inputs and produced candidates, but no full behavioral selection was completed. Old 1.1/1.3 and 2.1/2.2 are reopened for stronger validation and corrected algebra; their historical work is preserved below. No runtime rank extension belongs in this change.

## 1. Source validation and alignment

- [x] 1.1 Preserve historical source-ingest evidence: the prior run read the two artifacts into 40x5120 arrays. This establishes only that those bytes were consumed, not the safety/correctness of the current general storage-size heuristic.
- [ ] 1.2 Inspect the known `.pt` directions metadata without executing pickle and bind the narrow adapter to the reviewed content hash/layout from design D1. Verify key, dtype, shape, stride, offset, byte order and storage entry; reject unknown revisions/layouts. If access is unavailable, leave this task pending with the exact prerequisite.
- [ ] 1.3 Add extraction/row-validation fixtures with decoy equal-size storage, wrong layout/dtype, truncated payloads, nonfinite values, zero masks and unequal row norms. Verify all invalid inputs fail before output and valid rows are normalized explicitly before fusion.
- [ ] 1.4 Implement/report a common valid-layer comparison mask for the offset search, preserving all medians/counts/exclusions. Verify synthetic shifted directions recover their known alignment and empty support is not silently assigned an offset.
- [ ] 1.5 Reconcile measured direction availability with source weight-edit ranges and record separate masks. Update `docs/upstream-prs.md`/tool documentation with inspected provenance and the geometric-only interpretation of the old +1 result; verify no hook-equivalence claim remains.

## 2. Correct rank-one outputs and diagnostics

- [x] 2.1 Preserve the historical algebra finding that aligned equal-norm denoise and `subspace_k1` coincide. This justifies removing the duplicate candidate, not keeping two trials in a result table.
- [ ] 2.2 Normalize both participating rows, emit one denoise candidate, preserve anchor-zero masks and use the documented A fallback for unpaired production rows. Remove unused multi-rank output promises; verify unequal-norm fixtures, byte shape and unit/zero-row invariants.
- [ ] 2.3 Correct the orthogonal diagnostic to emit zero for absent/degenerate residuals and record norms before normalization. Test identical, opposite-after-alignment, near-identical and orthogonal pairs against the documented 1e-6 threshold; verify no original-direction fallback survives.
- [ ] 2.4 Remove unconditional `or True` checks and exercise the actual emitted candidates/metadata, not only isolated algebra. Verify one deliberately broken invariant makes the self-check fail and no rank-2/3 basis is flattened into a rank-1 file.
- [ ] 2.5 Include source/application identity, masks, offsets, per-layer source choice and pre-normalization norms in sidecars; identify A-alone and transported B-alone comparator files. Verify hashes/metadata match the exact emitted bytes and input validation completes before any candidate publication.
- [ ] 2.6 Update `dir-steering/README.md` with the reduced output list and diagnostic interpretation. Regenerate in a fresh task output directory; verify old user files are untouched and no stale `subspace_k1` is counted as another candidate.

## 3. Fair behavioral selection

- [ ] 3.1 Pin the corrected `401` site/revision and `402` protocol, development/holdout split, primary metric and guard margins. Allocate comparable scale-search budgets to both single sources and denoise; verify the manifest does not compare tuned fusion with an untuned source alpha.
- [ ] 3.2 Run the development comparisons and the orthogonal-only diagnostic through `402`. Verify all runtime controls pass and the diagnostic is not described as proof that adding a second basis would help.
- [ ] 3.3 Evaluate the selected production candidate against the strongest single-source comparator on holdout with complete A-E evidence. Record benefit/non-inferiority or a negative/inconclusive finding; verify fusion is not accepted merely for beating the weaker source or moving first-token mass.
- [ ] 3.4 Record the retained vector identity or the decision to keep a single source, with evidence references and measured settings. Verify docs/provenance say 'local runtime intervention', not reproduction of the external weight-edited model.

## 4. Integration

- [ ] 4.1 Run the tool's offline self-check and validate the generated f32/sidecars with `401`'s input contract; then run `openspec validate 404-fuse-msuiche-distributedcognition --strict`. Record which checks used synthetic versus real inputs.
- [ ] 4.2 Verify the final change is offline tooling/docs only and no runtime code was added for rank or a second hook. If shared test/Makefile integration changed, run the affected named tests; do not claim a new model parity run merely because the runtime diff is empty.

## Workflow follow-up

- A properly measured negative fusion result can close the research question. Missing source access or an unrun holdout cannot.
- Commit, push and archive require a separate explicit request.
