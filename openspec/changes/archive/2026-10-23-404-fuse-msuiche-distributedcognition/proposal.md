# Proposal

## Why

Two external V4.1 direction sets provide a testable fusion hypothesis, not proof that their derivation sites are interchangeable. The existing tool needs distinct, correctly formed candidates and a comparison against both single-source baselines before fusion can be accepted.

## What Changes

- Validate the known source tensor layouts, layer availability and finite values; normalize each participating row explicitly before fusion. Do not infer measured direction availability from the range of weights edited by a source publication.
- Keep the small source-to-source layer-offset search and record its geometric evidence, without treating its best cosine as proof of runtime-hook indexing or efficacy.
- Emit one `denoise` rank-1 candidate and one correctly defined orthogonal-residual diagnostic, plus reproducible single-source comparator files/metadata where conversion is needed.
- **BREAKING candidate cleanup:** stop emitting `subspace_k1` as a second candidate because it duplicates denoise for aligned unit inputs. Remove the promise that rank-2/3 subspaces fit in a one-direction-per-layer f32 file; two input directions span at most rank 2.
- Make a missing/zero orthogonal residual remain zero, record its norm before normalization, and test degenerate inputs rather than asserting success unconditionally.
- Compare fusion against both single-source vectors at the same declared application site, with comparable tuning budgets and held-out evaluation through `402`. A negative fusion result is a valid completion, not a reason to add runtime rank.

## Capabilities

### New Capabilities
- `steering-vectors`: validated offline direction conversion/alignment/fusion, with interpretable candidate metadata and measurement-gated selection.

### Modified Capabilities
None.

## Impact

- `dir-steering/tools/fuse_directions.py`, its model-less checks and candidate sidecars.
- `dir-steering/README.md` and source/provenance entries in `docs/upstream-prs.md`, updated with implementation.
- Depends on `401` for input/application identity and on `402` for acceptance. No dependency on `403`; a pinned constant-scale protocol is sufficient.
- No production engine/kernel change, no generic pickle execution and no required global dependency. Rank greater than one and permanent second hooks are outside this change.

## Closure (2026-10-23) — not adopted, no candidate left to produce

The fusion this change would build (msuiche + distributedcognition) is of two pre-1017 directions,
and `fused` itself is out of the race: it was the worst of the screened vectors for breadth on the
hardest prompts. The adopted direction is a bisector of two *1017* sources instead.

The fusion tool (`dir-steering/tools/fuse_directions.py`) stays; only this change's candidate is
dropped. No runtime code landed.
