# Spec Delta

## ADDED Requirements

### Requirement: Bounded read-only intervention observations
A steering diagnostic SHALL identify site, layer and token position and expose pre-edit projection, activation norm and relative intervention magnitude for a bounded selection. Disabled diagnostics SHALL add no diagnostic allocation/dispatch. Enabling observations SHALL preserve logits, KV and Engram bitwise under the same intervention, and overhead SHALL be measured.

#### Scenario: Probe preserves computation
- **WHEN** the same intervention runs with and without observation
- **THEN** its model state and logits match bitwise and the report separately identifies observation cost

### Requirement: Explicit alternative-site experiments
Experimental HC sites SHALL declare application boundary, indexing, operation and precision. Copywise and mean-only persistent edits SHALL be distinguished from the weighted-fold baseline and from each other. An alternative SHALL NOT silently replace the established baseline's semantics or reuse its acceptance evidence.

#### Scenario: Mean-only versus copywise edit
- **WHEN** distinct HC copies are used in an algebraic fixture
- **THEN** the mean-only edit preserves inter-copy differences within arithmetic tolerance, while the copywise edit is checked against its own per-copy projection

### Requirement: Measured layer masking
Initial layer-selection experiments SHALL use the existing zero-row mask convention with unchanged unit directions on active rows. Masks SHALL be selected on development data and assessed on holdout. Published layer profiles SHALL be treated as hypotheses, not required local outcomes.

#### Scenario: Published profile does not transfer
- **WHEN** a local layer-separation profile differs from the source publication
- **THEN** the difference is recorded without forcing the mask to reproduce that profile

### Requirement: Conditional continuous scales
A separate continuous per-layer scale mechanism SHALL be retained only if it improves on the measured simpler mask baseline. If retained, it SHALL validate all weights, include them in intervention identity and preserve default/no-file behavior bitwise. Direction magnitudes SHALL NOT silently stand in for validated scale parameters.

#### Scenario: Masks are sufficient
- **WHEN** continuous weighting has no established advantage over a binary mask
- **THEN** no new per-layer scale interface is required and the negative result is recorded

### Requirement: Locally derived direction evidence
A locally derived direction SHALL record the actual capture site, token-selection/pooling policy, example split and normalization. Initial validation SHALL include controlled benign contrasts and held-out task quality. Additive and projective experiments SHALL have distinct method/scale identities rather than treating a projective source file as an additive vector by default.

#### Scenario: Legacy capture hook is inactive
- **WHEN** a proposed extraction path does not reach the identified V4.1 site
- **THEN** the extraction is blocked or corrected before any resulting vector is accepted

### Requirement: Perturbation-aware specificity controls
Specificity experiments SHALL report seed, mask and observed activation perturbation for random and layer-permuted controls. Equal direction norm SHALL NOT be described as equal perturbation without measurement. Any dose calibration SHALL use development data and remain within validated parameter bounds.

#### Scenario: Unmatched random dose
- **WHEN** a random direction causes a much smaller activation edit and comparable dose cannot be established
- **THEN** the report names that limitation instead of claiming a perturbation-matched negative control

### Requirement: Held-out investigation decisions
Scale, index, generalization and failure-limit decisions SHALL use pinned protocols, paired uncertainty and held-out completed-response evidence where behavior is claimed. First-token mass, cosine and divergence SHALL be diagnostics, not standalone usefulness criteria. Contrary or inconclusive results SHALL remain valid recorded outcomes.

#### Scenario: Divergence and behavior disagree
- **WHEN** JS increases while task quality or the primary behavioral metric worsens
- **THEN** the candidate is not accepted merely because distribution shift increased

### Requirement: Conditional feedback controller
Event-based decay SHALL remain an experiment until a pre-edit observation predicts held-out outcomes beyond position/phase and a controller improves on the best measured simpler comparator. A retained controller SHALL define bounded scale, reset/fallback and session-state compatibility. A suppressed post-edit projection alone SHALL NOT establish that the behavioral decision is over.

#### Scenario: No predictive signal
- **WHEN** the observation adds no established predictive value or the controller does not improve the comparison
- **THEN** the result is recorded without adding a permanent event-decay option

### Requirement: Conditional attention-channel experiment
A second-channel experiment SHALL require a real active V4.1 application site and a direction validated for it. It SHALL be compared with the stronger single-site baseline before a control is retained. The presence of an inactive legacy attention flag SHALL NOT count as implementation of that site.

#### Scenario: Inactive attention option
- **WHEN** an experiment only varies the legacy attention flag without an active V4.1 hook
- **THEN** it is reported as an invalid experiment, not a measured neutral second channel
