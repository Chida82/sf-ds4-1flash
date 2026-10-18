# Tasks

> **IMPLEMENTATION HOLD.** Execute Group 6 first. The eight conceptual corrections
> are incorporated in the proposal, design and delta spec, but the underlying
> evidence reviews have not been completed. No code, vector generation, model run
> or dependency installation is authorized by this planning update. Passing
> OpenSpec validation or completing a review is not proof of an implemented feature.

All 24 task IDs are preserved; none is marked complete by this correction.
The former synthesis and retry recipes are replaced by proof obligations and
feasibility decisions. This prevents an agent from implementing a formula whose
claimed properties are false. Residual-write restoration also remains gated on
its contract review; no replacement runtime wiring is prescribed here.

Record **Findings / Evidence / Unresolved / Proposed next step** beneath each
review task when performed. Preserve historical files and raw grades. Use existing
tools and read-only calculations; synthetic or benign examples serve methodological
checks, not optimization of safety-refusal bypass. Additional artifact writes or
model-backed work require their own scoped authorization.

Order: Group 6 first; return its findings to the owner before continuing. Group 0
consolidates the audit; Groups 1-3 review their respective contracts and hypotheses;
Group 4 assesses validation readiness; Group 5 checks the resulting handoff. The
numbering intentionally retains old references rather than suggesting Group 6 runs
last. Do not commit, push, archive, install dependencies or run models automatically.

## 6. Scientific preflight (mandatory first)

- [ ] 6.1 Audit historical evidence and denominators. Read
  `eval/out/*-harmful-axis-a/manifest.json`,
  `openspec/changes/409-floor-operator-family/tasks.md`,
  `docs/steering-measurements.md` and design D1. Check record lengths and prompt
  identity before pairing indices, completions and grades; do not silently truncate
  with `zip`. Keep raw grades, quality flags, missing records, execution errors and
  invalid grades separate. Compare model/binary/vector identities, site, route,
  decoding and judge conditions, not just filenames and scale. Reproduce the
  corrected hard-15 raw/filtered inventory and identify incompatible cross-run
  combinations. **Verify:** an evidence note names run IDs, denominators, exclusions
  and disagreements; no historical grade or run is overwritten and no inventory
  union is presented as a deployed-policy result.

- [ ] 6.2 Independently verify the mathematical corrections in D3/D4. Derive the
  mixed-direction and separate-operation matrices and compare both basis inputs.
  Cover zero, identical, orthogonal and sign-reversed directions and singular or
  nearly singular Gram matrices. Distinguish a norm bound from contraction or
  semantic preservation. Check the `diag(2,-5)` eigenvalue-ordering and
  `diag(0.8,0.2)` minority-component counterexamples. Distinguish Gram-Schmidt,
  whitening and orthogonal Procrustes by their actual inputs and objectives.
  **Verify:** record formulas, numeric outputs, tolerances and which assertions
  are disproved; a test must not be changed to make an invalid equivalence pass.
  No direction, coefficient recipe or replacement optimizer is produced.

- [ ] 6.3 Audit capture semantics and coverage. Read `eval/capture_fold.py`,
  `eval/extract_floor_direction.py`, capture manifests under
  `eval/out/capture/{base,fused7,pool}/` and all `ds41_dump_fold_row` call sites in
  `ds4.c`. Identify tensor, position, layer, route, rounding and local operation
  order. Check the evidence for the "last 40 rows" assumption under chunking and
  reconstruction; do not infer semantic row ordering from file size alone.
  Recompute target-30/hard-15 intersections and join prompt identities where
  available. **Verify:** a coverage table and call-site references reproduce or
  explain differences from D6, including missing observations and the server/CLI
  mismatch; no absent feature is imputed or new capture generated.

- [ ] 6.4 Review independent validation and the evaluators. Identify which data
  were already inspected or used for parameter selection. Check that any proposed
  learned preprocessing, feature selection and thresholds exclude validation/test
  examples. Plan blinded review of grade/filter disagreements on benign tasks,
  including legitimate code repetition and multilingual text. Keep correctness,
  format compliance, degradation and safety outcomes distinct. **Verify:** the
  note states prior exposure, split requirements, fitting boundaries, paired
  uncertainty and missing/invalid-grade handling. It does not claim that low
  dimension, leave-one-out alone or a small smoke suite prevents overfitting.

- [ ] 6.5 Review numerical stability independently of behaviour. On synthetic or
  existing benign data, define or calculate effective rank, retained-subspace
  condition number, eigenvalue gaps and principal angles. Record normalization,
  rank tolerance and sample count. Check sensitivity to removing/resampling
  examples; distinguish arbitrary sign changes and degenerate eigenspace rotations
  from genuinely different effects. **Verify:** the note includes a known-rank
  synthetic case and measured sensitivity or an explicit evidence gap. No small
  angle or stable spectrum is claimed to guarantee correct responses; no candidate
  directions are synthesized and no dependencies installed.

- [ ] 6.6 Reconstruct router/gate/loop evidence. Reconcile `409` task 7.6's
  "not run" statement with `20261017-174844-harmful-axis-a` and available logs,
  including `hold_from_layer`, binary identity and recorded controls. Distinguish
  observed flags from hypotheses about their cause. Separate offline classification,
  held/in-graph selection, retries and repeated transformer blocks. Check D5's
  information boundary with a benign false-positive example and list the timing
  and state evidence needed to assess cost. **Verify:** classify each historical
  claim as observed, hypothesis, contradicted or untested; no whole method family
  is rejected merely because one variant failed or a test was absent. Return the
  preflight findings and unresolved decisions to the owner; do not launch a live
  fallback or recurrence experiment.

## 0. Consolidate the retrospective protocol and evidence

- [ ] 0.1 Document the corrected protocol after preflight review. Preserve the
  panel-30 in the proposal and report `23` separately. Label the panel and its
  hard-15 subset as retrospective/development data. Record the distinction between
  the descriptive raw/filtered score, independent capability evaluation and safety
  outcomes; preregistration concerns future decisions only. **Verify:** the protocol
  identifies dataset/selector hashes, scorer version and compatible run conditions,
  and cites D1/D7 without relabelling previously inspected data as held-out.

- [ ] 0.2 Specify the evidence comparison contract before any helper is written.
  A future `eval/compare_vectors.py` may render the audited records, but cannot
  identify a configuration by vector stem and scale alone. Specify strict alignment
  of selector, prompt, response and grade, complete intervention identity, duplicate
  handling, errors/invalid grades and per-metric denominators. Preserve all raw
  labels and flags beside any derived credit. **Verify:** synthetic record examples
  cover a length mismatch, missing grade, conflicting duplicate, different binary,
  flagged COMPLY and partial coverage; their expected report/error is explicit.
  Do not implement or run the old helper command if the helper does not exist.

- [ ] 0.3 Produce the attributable historical summary from compatible evidence.
  Use the D1 run references and preflight findings, with separate views for raw
  grades, heuristic-filtered grades and cross-run inventory. State which records
  are reusable, which require qualification and which are unavailable. Preserve
  the disputed `24` grade pending separate adjudication. **Verify:** every total
  has a denominator and source IDs; the hard-15 inventory is not labelled 15/15
  filtered success or executable-policy performance. If recalculation differs
  from D1, report the cause rather than forcing the expected count.

## 1. Residual-write contract review (restoration remains deferred)

- [ ] 1.1 Review admission and persistent-state requirements against existing
  engine/frontends and the delta spec. Identify the expected interface and all
  independently unsupported settings; retain opt-in precedence, validation and
  save/load/reuse guards. Do not invent a new disable switch or assume an obsolete
  function signature from the historical experiment. **Verify:** an interface and
  rejection matrix names existing versus proposed behaviour and missing evidence;
  no flags or source fields are added during this review.

- [ ] 1.2 Review the numerical/site contract against D2. Distinguish attention,
  shared-expert and summed MoE outputs; a common file shape does not make these
  sites equivalent. Record operation/rounding order and which decode, batch,
  reconstructed and distributed routes would need separate evidence. Do not treat
  projection of separately rounded terms as bitwise projection of a rounded sum,
  or checkpoint-diff recovery as exact output-edit equivalence. **Verify:** the
  contract states which properties are exact arithmetic identities, tolerance
  checks or same-schedule bitwise controls, and which routes remain unverified.
  The earlier line-by-line restoration recipe is not an implementation instruction.

- [ ] 1.3 Specify the control-test matrix for any future restoration. Include
  disabled and zero-scale controls against the otherwise identical run, an active
  fold plus zero write against fold-only, synthetic unit-direction arithmetic,
  zero rows, unsupported inputs and persistence refusal before mutation. Separate
  helper agreement from whole-model state equality and coverage. **Verify:** every
  proposed test names inputs, expected outcome/tolerance and whether it already
  exists or would need implementation; a counter or nonexistent make target is
  never accepted as evidence that a route passed. No model-backed test is run here.

## 2. Mathematical-method feasibility (no synthesis recipe approved)

- [ ] 2.1 Resolve method names and required data using D3 and preflight findings.
  For each of Gram-Schmidt, whitening and orthogonal Procrustes, identify the
  input objects, coordinate convention, objective and testable output property.
  State whether paired observations for Procrustes or an identifiable covariance
  for whitening exist. A reference-vector Gram matrix and an activation covariance
  must remain distinct. **Verify:** the method note has an explicit missing-data
  or not-applicable result where appropriate; it does not call heuristic weighting
  Procrustes or claim that orthogonalization performs whitening.

- [ ] 2.2 Replace the former `1/7` synthesis acceptance test with an independent
  arithmetic counterexample. Verify D3 on each basis input, showing off-diagonal
  coupling and the difference from separate operations. Check norm, rank and sign
  behaviour; test the invariance of `dd^T` under sign reversal separately from the
  sign sensitivity of vector addition. **Verify:** the note demonstrates the
  non-equivalence and withdraws any inherited result for a mixed vector. The
  formerly named `v41-whiten-*` output files are not generated or promoted.

- [ ] 2.3 Resolve the distillation problem statement before selecting an estimator.
  Following D4, distinguish summarizing target scatter from approximating a
  matched input-output transformation. Document the intended quantity, loss,
  units, scale normalization and admissible operator, or explicitly record that
  they are unresolved. Identify how any proposed target would be measured; do
  not invent one by replacing a different-site intervention with the D3 blend.
  Include the algebraic-versus-magnitude eigenvalue and minority-component test
  cases. **Verify:** a bounded decision note states supported observations and
  unresolved prerequisites. The former power-iteration, coefficient and angle
  recipe is withdrawn, with no substitute optimizer or generalization guarantee.

## 3. Router, gate and retry feasibility (no live policy approved)

- [ ] 3.1 Review feature and label availability, not a presumed router fix. Build
  an evidence map from the capture coverage in D6 and compatible historical labels.
  Distinguish pre-current-intervention values from previous-layer effects, fixed
  versus fitted transformations, and arbitrary tie labels from measured outcomes.
  Do not train/evaluate a claimed post-intervention router where matching captures
  are absent, or infer continuous mix coefficients from discrete winner labels.
  **Verify:** the map names available inputs at decision time and unavailable
  fields, with the historical classifier's limitations and causal uncertainty.
  The old `polymorphic_router.py` prescription is not implemented.

- [ ] 3.2 Review retry observability and state semantics on benign synthetic cases.
  Specify the information visible to a diagnostic selector and which final-answer
  properties are evaluation-only. Any proposed observation window must have one
  declared unit/boundary; absent token metadata means token-exact replay is unknown.
  Include a false-positive trigger selecting a worse answer, a late quality defect
  invisible in the prefix, and a stopped process without a resumable session.
  **Verify:** the cases expose possible regressions, future-information leakage
  and unmeasured costs. No phrase-list guarantee, hard-coded window, automatic
  fallback schedule or live `polymorphic_loop.py` implementation is prescribed.

## 4. Evaluation readiness and missing evidence

- [ ] 4.1 Separate oracle inventory from executable-policy evaluation. Using the
  historical summary, specify which reported upper bounds use knowledge of all
  outcomes and which, if any, correspond to a selection made with observable
  information only. Report missing alternatives and incompatible conditions.
  **Verify:** no task asserts a policy must reach 13/14/15 successes simply because
  those outcomes exist across candidates; unsupported executable-policy results
  are labelled unmeasured, not filled from the oracle.

- [ ] 4.2 Produce the missing-evidence list rather than blindly scheduling only
  missing prompt IDs. Distinguish absent records from existing records with
  incompatible binary, model, template, decoding, judge or intervention identity.
  List missing controls and captures as well as grades. **Verify:** each gap has
  its reason and the claim it blocks, and no historical record is silently reused
  as current acceptance. Any additional data collection needs separate scope and
  authorization; this task does not launch the earlier harmful-prompt commands.

- [ ] 4.3 Assess independent validation readiness for any later benign-capability
  study. Following D7, identify untouched examples, related-prompt grouping,
  fitting/selection boundaries and a fixed reporting protocol. If an untouched
  set is unavailable, report that limitation rather than repurposing the panel-30
  or its hard-15 subset. **Verify:** the readiness note records data provenance,
  prior exposure, required splits, paired uncertainty and separate capability,
  quality and safety outcomes; no parameter or candidate is tuned on the test set.

- [ ] 4.4 Review cost and acceptance evidence without selecting a default. List
  actual measurements versus estimates for engine startup, prefill, continuation,
  retries, feature readback, buffering and total latency. Include discarded work
  and distinguish a historical selected-set rate from a workload retry rate.
  **Verify:** a readiness table states measured/unmeasured for each required
  quality, safety and cost dimension; there is no zero-overhead assumption,
  automatic score-based adoption or claim that six benign smoke cases suffice.

## 5. Provenance, documentation and handoff

- [ ] 5.1 Review provenance and promotion eligibility. Check source hashes,
  derivation method, layer mapping and experimental identities of existing files;
  distinguish file validity from behavioural validation. **Verify:** any missing
  provenance or independent evaluation is named, and no synthesized candidate is
  copied into production assets or promoted merely because its file is valid or
  a retrospective score is higher.

- [ ] 5.2 Prepare attributable documentation corrections from the completed
  reviews. Keep historical run evidence unchanged; distinguish proposed flags and
  tools from implemented ones and do not advertise withdrawn synthesis/retry
  recipes. **Verify:** the proposed documentation changes identify their source
  evidence and affected paths, and agree with the proposal/design/spec on each of
  the eight corrections. Updates outside these planning artifacts require their
  own scoped authorization.

- [ ] 5.3 Check the handoff as a whole. Run
  `openspec validate 410-net-improvement-write-site --json` for format validation,
  then review mathematical claims, counts, identity/coverage, observation timing,
  unresolved decisions and task status manually. Existing runtime regression,
  persistence and parity evidence cannot stand in for tests of an unimplemented
  site. **Verify:** the handoff lists completed reviews and unresolved prerequisites
  separately, identifies any future implementation scope needing approval, and
  leaves absent model-backed results unmeasured. No code, vector or production
  behaviour is claimed complete merely because the artifacts validate.

## Workflow follow-up

- Return the preflight results to the owner before further work. Runtime restoration,
  new benign experiments or an implementation plan require resolved prerequisites
  and separately approved scope.
- Do not archive/sync this delta as implemented behaviour while its pending runtime
  contracts are unmet. Any scope reduction or deliberately deferred requirement
  must be agreed and reflected in the artifacts, not hidden by checking tasks off.
