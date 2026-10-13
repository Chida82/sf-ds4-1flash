# Design

## Context

See proposal.md for scope. The existing script reads one matching-size storage from a torch ZIP, aligns signs, searches offsets and emits denoise/ortho/subspace_k1. Historical input conversion and an offline algebra check were reported successful. The reported median cosines were 0.579, 0.688 and 0.779 at offsets -1, 0 and +1; no complete behavioral selection followed.

Those numbers concern source-to-source vector geometry. `401`'s application is a weighted attention-input fold, not a verified copy of either published derivation site. A best offset does not establish a sublayer equivalence or change `401`'s runtime index.

Current algebra/validation gaps: denoise does not normalize B before addition; the zero orthogonal-residual case falls back to A; reported residual norms are computed after normalization; identical-source SVD can include a zero second basis vector; one assert ends in `or True`. The serialized tensor's shape/stride/key are not established merely by finding storage of the right byte length.

## Goals / Non-Goals

**Goals:** validated rank-1 candidates, honest diagnostics and a fair comparison with the strongest single-source baseline.

**Non-Goals:** reproduce weight-edit abliteration, implement a multi-direction runtime, derive new vectors, assume low cosine proves complementary behavior, or ship a general torch checkpoint loader.

## Decisions

### D1. A narrow, fail-closed source adapter

For the msuiche input, use the validated converter output and its content/shape metadata. Validate finite rows, explicit zeros/masks and row dimensions before algebra.

For the `.pt`, inspect the tensor descriptor without executing pickle. Bind the narrow storage reader to the reviewed source content hash and verified `directions` key, dtype, shape, stride, storage offset, byte order and storage entry. Record that reviewed layout/hash with provenance and tests. Reject an unrecognized source revision/layout instead of guessing by storage size or implementing a generic pickle VM. Standard-library `pickletools` can aid inspection; an unreadable/gated artifact is a named prerequisite, not permission to invent metadata. Synthetic fixtures exercise extraction through the same validated layout contract.

No generic `pickle.load` on downloaded content. A one-off inspection requiring additional tools must use a disposable task environment, not a persistent host dependency. The normal supported-artifact extraction remains dependency-light.

The published abliteration target range L4-36 describes weight edits; it is not evidence that measured directions outside that range are missing. Determine actual tensor rows and documented source masks from the inspected artifact. Report both measured availability and any deliberate experimental mask separately.

### D2. Source offset is a hypothesis with a fixed comparison mask

For offsets -1, 0 and +1, compare `A[L]` with `B[L+offset]`, unit-normalizing and sign-aligning before cosine. Use a common valid-layer comparison mask across offsets when selecting the median so edge exclusions cannot silently bias the winner; record the mask, counts and excluded rows. If there is no adequate common support, report that the automatic offset is unresolved and require an explicit experiment choice rather than silently selecting the first offset.

Record the selected offset and all candidate medians. Preserve the historical +1 result as historical geometry; a stricter mask/loader may change it. Neither the offset nor high cosine validates applying B at A's site. Runtime-site/index experiments remain `405`'s responsibility.

### D3. Only distinct rank-1 outputs

For a valid pair, set `a=unit(A[L])`, `b=unit(B[L+offset])`, flip b when their dot product is negative, and compute `unit(a+b)` for denoise. The sign of a projective direction alone is immaterial; sign alignment matters when adding sources.

Where B has no valid pair, the production denoise candidate keeps A's validated row and records the fallback. Where A is masked/absent, keep that row zero; do not unexpectedly activate a layer outside the declared anchor mask.

Do not emit `subspace_k1`: for these equal-weight aligned unit inputs it is the same denoise direction. Do not advertise k=3 from two per-layer directions, and do not flatten a rank-2 basis into a format whose runtime applies one row. Keep no unused generic SVD/rank interface merely for later work.

### D4. Orthogonal residual is a diagnostic, not a fallback model

Compute `r = b - dot(a,b)*a` only where both sources have valid aligned rows. Save `||r||` before normalization. If the row is unpaired or `||r|| <= 1e-6` for these unit inputs, emit an all-zero diagnostic row and mark it absent; otherwise emit `unit(r)`. The threshold must appear in metadata and fixtures, so floating-point noise from nearly identical rows does not become a full-strength random-looking direction.

Do not substitute A when r is zero: that changes 'no new component' into 'apply the original component'. A rank-1 ortho-only run can characterize the residual but cannot by itself prove that adding it to A improves a two-direction intervention. This change does not implement that rank-2 experiment.

### D5. Metadata and finite geometry before writing

Record source content hashes and inspected layout identifiers, original derivation hooks, application hook/revision from `401`, offset/comparison mask, per-layer original norms/cosines/source selection, pre-normalization residual norms and output hash/shape. Validate every input/candidate before publishing outputs; reject malformed/empty unsupported inputs without partial candidate files.

Write candidates to a fresh output directory for comparisons. Stop generating the duplicate filename; do not automatically delete pre-existing user files from an earlier run. Document that stale generated outputs must not be counted as new candidates. All-zero diagnostic files are valid controls and must not be normalized into nonzero rows.

### D6. Compare against both sources fairly

Produce/identify A-alone and transported B-alone comparator files at the same explicit runtime site, alongside denoise and ortho diagnostic. They are local runtime interventions, not replicas of either external weight-edited model. Preserve per-candidate masks and hashes in `402` manifests.

Use one development/holdout split, the same primary metric/guard margins and comparable scale-search budgets for each eligible production candidate. Do not compare a tuned fusion against A at an inherited unsuitable alpha. Select a candidate once on development data, then evaluate it against the best single-source comparator on holdout. Retain fusion only on the declared benefit with B/C/D non-inferior; otherwise keep the stronger measured single source and record the negative/inconclusive result. E remains a domain report, not a blended score.

## Risks / Trade-offs

- [Gated/revised serialized source] -> supported-content/layout contract, explicit rejection and a pending prerequisite when inspection is unavailable.
- [Unit normalization amplifies tiny residual noise] -> retain raw residual norms and zero below the documented threshold.
- [Offset search overfits geometry or behavior] -> fixed comparison mask, separated tuning/holdout and no equivalence claim.
- [Extra runtime rank seems an easy follow-up] -> outside scope; first finish the fair rank-1 comparison.

## Migration Plan

Correct loader/algebra and their tests before regenerating candidate files and rerunning `402`. Old denoise/subspace_k1 outputs count as one geometric candidate, not two confirmations. Update candidate naming and provenance alongside the tool. No runtime or cache migration occurs except the changed vector content naturally receiving a new `401` identity.
