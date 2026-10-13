# Tasks

Depends on `400`. `402` can be built in parallel; it is not required to write kernel/state correctness checks. This checklist supersedes the old compound boxes: old 2.3 was partial, old 3.1 checked only a completion, old 3.2 was a first-token screen, and old 5.1 included unrun parity. Historical results are retained in design.md, not promoted to new acceptance. Every unchecked task needs its own evidence; no implementation is authorized by this file alone.

## 1. Converter and input contract

- [x] 1.1 Preserve the existing valid-artifact conversion: the recorded real input produced 819200 bytes, row 0 zero and 39 unit rows. This establishes the happy path only, not complete malformed-input rejection.
- [ ] 1.2 Harden `controlvector_to_f32.py` for the exact layer set, duplicates/aliases, metadata consistency, supported GGUF layout, bounded tensor storage and finite unit rows. Extend its self-check with missing middle/last layers, NaN/Inf, duplicate rows and truncated storage; verify no output is written on rejection.
- [ ] 1.3 Replace indistinguishable fixture rows with distinct unit directions; verify exact row mapping and byte shape. Write separate source/application-hook metadata, source alpha, intervention revision and content hash; verify metadata does not imply hook equivalence.
- [ ] 1.4 Validate active raw files and API scales at the engine boundary using the same documented norm tolerance, allowing zero mask rows and requiring zero row 0. Add malformed-size, nonfinite and non-unit tests and confirm errors occur before graph upload.
- [ ] 1.5 Update converter/help documentation alongside these changes; verify it calls 4-8 historical screening candidates, not defaults, and distinguishes raw-file limitations from sidecar provenance.

## 2. Site semantics and complete graph coverage

- [x] 2.1 Preserve the implemented decode/ordinary-batch plumbing: source inspection shows direction upload/free and pre-attention projection on the active `ds41_*` graph. This is not acceptance of its current rounding order or reconstruction coverage.
- [ ] 2.2 Write the route-agreement fixture (design D2/D7): one synthetic folded row through the decode and the batch projection routes, compared at FP32 tolerance, plus zero rows and projection factors on one-row and multi-row inputs. Record whether the routes agree.
- [ ] 2.3 Only if 2.2 shows a difference beyond tolerance: move the batch fold rounding before the projection with no second rounding before normalization, bump the intervention revision and leave disabled arithmetic unchanged. If the routes agree, record that and change nothing.
- [ ] 2.4 Cover the batch branch of `ds41_decoder_prepare` before normalization and check all callers, row graph copies and views. Add a regression that fails if reconstructed inputs skip or double-apply steering, including the ordinary short-wide suffix route.
- [ ] 2.5 Add the isolated CPU reference and mirror the edit at the corresponding existing reference fold where applicable. Verify synthetic reference-versus-Metal checks with explicit FP32 tolerances; confirm full CPU V4.1 admission is not enabled and no large CPU model run is used.
- [ ] 2.6 Update the site description in code/help, `dir-steering/README.md`, affected agent notes and `docs/upstream-prs.md`. Verify the description says weighted fold, after Engram where present, direct index baseline, and no published-replication claim; remove the incorrect 24.5K-only coverage note.

## 3. Frontend and live-control errors

- [x] 3.1 Preserve CLI/server residual-scale parsing and suppression of implicit FFN=1 when residual is explicitly set; the existing option branches establish this implementation.
- [ ] 3.2 Reject unsupported nonzero FFN/attention settings after the original no-opt-in refusal. Verify explicit residual with zeros succeeds, file-only implicit FFN fails helpfully, and no-opt-in still produces upstream's exact line.
- [ ] 3.3 Make the live FFN setter and `/steer` truthful on V4.1 without deleting their API/tooling. Verify a nonzero request fails without changing the session, and help does not advertise residual live control that does not exist.

## 4. Steering and persistent state

- [ ] 4.1 Refuse active steering together with persistent KV reuse and snapshot save/load (design D6): one guard before any session mutation, one clear error naming the limitation. Verify a steered server session with a configured KV root neither reads nor writes under it, snapshot save/load fails before mutation, zero-scale sessions behave exactly as today, and existing cache files are untouched. Document the limitation with the guard.

## 5. State-level controls and enabled acceptance

- [ ] 5.1 Extend the existing V4.1 graph test/Makefile entry points with baseline, opt-in/no-file, real-vector/zero-scale, zero-vector/nonzero-scale and disabled-switch cases. Verify each applicable no-op compares 65 decode steps of logits, KV and Engram bitwise and checks allocation behavior; keep model-less fixture tests separately runnable.
- [ ] 5.2 Execute the state controls under SSD streaming and retain the named output plus command/model/vector identities. If the slow-path zero-vector control fails, resolve the arithmetic cause before efficacy runs.
- [ ] 5.3 Execute enabled coverage at exact token counts selecting scalar, batch, 3072/4096 short-wide, 8192 wide and a deferred-decoder route, plus append and the refusal of snapshot/persistent reuse while steered. Record actual route coverage and check reconstruction-specific assertions; do not claim different upstream schedules must have identical whole-model logits.
- [ ] 5.4 Measure enabled prefill/decode overhead against the same build with steering off at a fixed expert cache. Record intervention identity and timing conditions; document overhead instead of inferring it from the small projection kernel.
- [ ] 5.5 Hand off the intervention identity to `402` and rerun its minimum protocol. Record efficacy as preliminary until full axes are available; do not reuse the old first-token numbers as acceptance, and if 2.3 changed the arithmetic, remeasure under the new revision.

## 6. Integration

- [ ] 6.1 Run `make test`, reading the names/results of the tests actually executed, the added model-less steering checks, and `openspec validate 401-residual-steering-hook-msuiche --strict`. Record build versus runtime checks separately.
- [ ] 6.2 Run disabled-path upstream parity against the actual candidate worktree/build with SSD streaming. Verify token identity and the speed guard; a completion-only or historical run does not close this task.
- [ ] 6.3 Review the touched source region and check every requirement/scenario against evidence. Verify docs, intervention revision and the persistent-state guard describe the final code, and no unsupported site is silently accepted.

## Workflow follow-up

- `402` owns full behavioral acceptance; `405` owns alternative-site and index experiments. Neither is a reason to bypass this change's correctness controls.
- Commit, push and archive require a separate explicit request.
