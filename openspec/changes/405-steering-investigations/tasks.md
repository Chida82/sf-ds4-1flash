# Tasks

Depends on corrected `401` and the applicable `402` protocol. Only event-decay comparisons may depend on a retained `403` schedule; observations/sites/masks/vectors do not. No items were implemented in the original checklist. The old projection-log group moves first, old scale/index rigor work moves before selection, and mandatory per-layer/event knobs become conditional.

Each experiment is completed by evidence and a supported/rejected/inconclusive decision, not by implementing a knob. Conditional implementation tasks can close with a documented failed adoption gate and no code, but unrun experiments remain open. Use `402` records/metrics rather than introducing another runner.

## 1. Observe the actual intervention

- [ ] 1.1 Define a bounded diagnostic record for site/revision, layer/token/phase, pre-edit dot, activation norm, intervention norm and their ratio. Add synthetic checks of the projective magnitude relation and zero inputs; verify the record distinguishes pre-edit and post-edit quantities.
- [ ] 1.2 Implement the minimum read-only capture using the existing reduction when safe or a separate diagnostic pass, with buffered bounded output. Verify no diagnostic allocations/dispatches occur when off and no wait is introduced for every scalar by default.
- [ ] 1.3 Classify any probe env and document selection/bounds/units alongside the implementation. Run same-intervention probe-on/off 65-step logits/KV/Engram comparisons and measure overhead; verify bitwise identity and publish actual cost rather than claiming the scalar is free.

## 2. HC site comparison and scale/index recheck

- [ ] 2.1 Pin F (corrected weighted fold), R (copywise persistent pre-Engram) and M (mean-only persistent pre-Engram) as distinct task-local candidates. Verify tensor layout/strides and prototype R with the existing multi-row projection where valid; add synthetic mean/inter-copy-difference checks for both alternatives.
- [ ] 2.2 Verify each candidate's single/batch/reconstruction coverage and zero-intervention controls before behavioral work. Record site, boundary, precision and index identities; confirm no candidate silently redefines the `401` public baseline.
- [ ] 2.3 Run a bounded site comparison with fixed vector/mask/index/prompt policy and comparable development tuning budgets using `402`. Record complete-response effects, guard metrics and measured activation dose; verify a source-alpha or first-token comparison alone cannot select a winner.
- [ ] 2.4 Revisit the historical scale and index hypotheses with prompt-paired uncertainty, at least the former 25-prompt screen coverage and a separate holdout for selection. Include zero/removal/reflection reference scales; verify d versus -d is a projective no-op and keep source-fusion offsets separate from runtime indexing.
- [ ] 2.5 Record site/index conclusions and evidence in this design's results section and appropriate user-facing experimental notes. Verify any recommendation to promote a different site names the contract/identity changes required before promotion, rather than silently changing `401`.

## 3. Layer masks before new scale formats

- [ ] 3.1 Measure the local per-layer projection/separation profile with the probe. Record observed agreement/disagreement with published priors; verify the result is not forced to match a source profile or to classify layer 14 as part of L1-6.
- [ ] 3.2 Generate a bounded set of early/middle/late and leave-block-out masks by zeroing existing f32 rows. Add byte/shape/unit-row tests and metadata hashes; verify no new runtime option or scaled non-unit row is needed for binary masks.
- [ ] 3.3 Compare masks on development data and assess the chosen mask on holdout against the stronger unmasked comparator. Verify primary behavior and quality margins through `402`; document the mask or negative/inconclusive result with its exact layer set.
- [ ] 3.4 Only if binary-mask results justify finer control, run a task-local continuous-weight experiment and assess its benefit. If retained, validate scale inputs, update state identity and test default/no-file bitwise behavior with docs; otherwise record non-adoption and add no scale-file interface.

## 4. Directions derived at the real site

- [ ] 4.1 Select controlled benign contrast pairs and pin capture site, token-selection/pooling rule, normalization and train/development/holdout split. Verify the chosen capture call sites are active V4.1 paths, not legacy hooks retained for another purpose.
- [ ] 4.2 Reuse/extend existing extraction tooling for a local difference-of-means baseline with bounded captures. Add distinguishable-layer synthetic fixtures and record source/example hashes; verify exact row mapping and deterministic extraction before a model-derived vector is used.
- [ ] 4.3 Evaluate the local direction on complete held-out benign behavior and task correctness using `402`. Record a measured benefit or negative result; verify a changed output style does not hide failure of the underlying task.
- [ ] 4.4 If useful to separate method effects, compare a properly derived additive contrastive baseline with the projective candidate in task-local code. Verify separate sign/scale/site identities and quality guards; do not reinterpret the external projective controlvector as additive. Document the result without shipping a method selector by default.
- [ ] 4.5 Decide the layer-id base convention for an own-derived vector and prove it against the runtime. msuiche's GGUF exposes the ambiguity: the key `glp.layer_ids_zero_based` is named zero-based but lists the 1-based `direction.N` indices (a misnomer `402` worked around by parsing the values, not the name). Verify empirically whether the runtime maps `direction.N` to layer N (row N, the current converter and `--dir-steering-file` contract) or to layer N-1, by steering a single known layer and reading the per-layer projection norms from task 1.1; record whether capture layer k and application row k coincide. Pin one convention in the derivation tooling and its sidecar, and state plainly whether "zero_based" was a naming slip or a real off-by-one, so an own vector does not inherit the ambiguity.

## 5. Specificity, generalization and limits

- [ ] 5.1 Add multiple seeded random and layer-permuted controls through the existing `402` runner, preserving masks. Calibrate any dose matching on development activations and within supported scale bounds; verify the report distinguishes equal-vector-norm, measured-dose-matched and unmatched controls.
- [ ] 5.2 Run the pinned generalization map over declared domains, languages/templates and prompt/output lengths, with reasoning/image repeats only where claimed. Verify complete-response primary metrics, quality guards and per-domain counts are reported separately.
- [ ] 5.3 Map the first observed repetition, code-switching and task failures over a bounded scale/length grid, including historical scale 16 only as a candidate. Preserve inspected responses and uncertainty; verify a small benign spot check is not called a validated safe range.
- [ ] 5.4 If reporting first-token JS, reuse `402`'s valid support/full-distribution machinery. Test that missing top-k support cannot become an exact divergence; explain disagreements with semantic metrics without requiring matching rankings.
- [ ] 5.5 Record the specificity/generalization decisions and evidence references in this design/results documentation, using performance records only for actual timing findings. Verify no separate status ledger or unsupported source-transfer guarantee was introduced.

## 6. Event decay only after predictive evidence

- [ ] 6.1 Test whether the pre-edit observed signal predicts held-out outcomes beyond token position/phase. Check orientation consistency and compare with post-edit suppression as a confound; record predictive value or a failed gate before implementing feedback.
- [ ] 6.2 Only if justified, prototype a bounded non-increasing-per-phase event controller against the best measured constant/window or retained `403` comparator. Test resets, noise/fallback, session isolation and snapshot state; otherwise record non-adoption with no event flag.
- [ ] 6.3 Evaluate the controller on holdout using `402` and record adoption/non-adoption with complete guards. Verify any retained mechanism has truthful identity, tests and docs, and that `403` is not treated as implemented when it retained no schedule.

## 6A. Projection-nulling: adaptive gain at the fold site

Depends on 1.1-1.3 (the diagnostic probe). The current fold adds a fixed `scale × direction[layer]` regardless of how much refusal signal the residual carries. Projection-nulling replaces the blind magnitude with measured dose: `proj = dot(residual, direction[layer]); residual -= clamp(proj, 0, cap) × direction[layer]`. This removes exactly the refusal component present (up to `cap`), cannot over-subtract by construction, and makes vector comparison fair (isolates direction accuracy from magnitude tuning). Motivated by the 408 axis-A finding: audreyt at scale 6 broke on the 7 hardest prompts (sovra-steering) while producing higher COMPLY on the rest.

- [ ] 6A.1 Correlate the probe's per-layer `proj / ‖residual‖` ratio with the 7 audreyt errors vs the 23 ok completions at scale 6. Confirm that the errors cluster at the highest ratios. If they do not, record a negative finding and do not proceed to 6A.2. This is offline analysis on existing run data, no model needed.
- [ ] 6A.2 Implement projection-nulling with cap in the existing fold site (`ds4.c`, post-Engram pre-norm). Gate behind `--dir-steering-adaptive` (or env `DS4_STEERING_ADAPTIVE_CAP`); default off, fold unchanged. Add a decode-switch parity test (`DS4_METAL_DISABLE_V41_ADAPTIVE_STEERING=1` restores the fixed fold, bitwise identical). Expected cost: one dot product (5120 elements) per layer per token, ~0.016% of token compute.
- [ ] 6A.3 Tune `cap` on the development set using the `402` protocol. Compare projection-nulling vs fixed-scale on the same vector (msuiche) at matched REFUSE rate. The key metric is DEFLECT→COMPLY conversion without introducing errors. Record the cap knee and whether it replaces the scale sweep.
- [ ] 6A.4 Re-evaluate audreyt and fused-denoise under projection-nulling. If the 7 errors disappear and COMPLY rates converge across vectors, record that the mechanism dominates vector choice; otherwise record the residual vector-dependent differences.

## 7. Attention second channel only after a real-site gate

- [ ] 7.1 Establish a measured limitation of the stronger residual-only candidate and locate an active V4.1 attention-output site/direction suitable for testing. Verify call-site reachability and source-site compatibility; varying an inactive legacy flag must fail the experiment setup.
- [ ] 7.2 Only if that prerequisite is met, run a bounded task-local residual-plus-attention comparison with controls and fair dose tuning. Verify benefit over the stronger single-site comparator with `402`, or record a negative/inconclusive result; do not ship an attention knob before this gate.
- [ ] 7.3 Document any justified follow-up with its required active hook, identity and acceptance evidence. Verify no absent second channel is described as a measured neutral or implemented feature.

## 8. Prefill-phase and reference-model investigations

- [ ] 8.1 Per-layer prefill projection probe (read-only): at the last prompt position, dump the residual's projection onto the accepted refusal direction across layers, for base vs steered and for refusing vs benign prompts. Identify which layers carry the refusal during prefill and whether the 40-layer vector covers them. Measured overhead, unchanged off path; no scores, just the projection trace.
- [x] 8.2 Prefill-vs-decode dose ablation: steer the prefill only, the decode only, and both, and measure the first-decision refusal flip to isolate where the dose does the work (the fold already runs in `ds41_before_attention_batch`, so the prompt is steered at the start scale today). A task-local switch, not an always-on knob; record which dose removes the refusal. Done: `DS4_STEERING_PHASE` toggle (`c645037`); 8-token screen N=30 (`docs/steering-measurements.md` 2026-10-15): decode-only = base (1.00, no effect), prefill-only = 0.40 (82% of removal), both = 0.27. Decision is at prefill; decode is a secondary boost on borderline prompts → supports a decaying dose.
- [ ] 8.3 Reference-model as a source of compliant contrast text: use a known less-refusing model only to produce the "direct/compliant" pole, then derive the contrast direction in V4.1's own prefill activations (not a cross-model residual diff — the spaces do not align). Record pair source/count; feeds `407`.

## 9. Integration and handoff

- [ ] 9.1 Run model-less/kernel checks, `make test` with named output, probe no-op state checks and disabled-path parity for retained runtime changes; run `openspec validate 405-steering-investigations --strict`. Distinguish task-local prototype evidence from release validation.
- [ ] 9.2 Review every retained probe/mechanism and every conditional non-adoption against the spec. Verify unused experiments did not become release flags, evidence-backed negative outcomes are explicit, and no unexecuted model-backed work is checked off.

## Workflow follow-up

- Reconcile any proposed promotion that changes the fixed `401` contract before applying it to release behavior; an experimental winner is not permission for a silent semantic switch.
- Commit, push and archive require a separate explicit request.
