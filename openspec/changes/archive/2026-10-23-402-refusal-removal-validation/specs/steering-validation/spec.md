# Spec Delta

## Purpose

Make steering experiments reproducible and auditable through KPI-first evaluation, separating intervention effects, model quality, measurement failures and explicit content inspection. Qualify the same runner contract for future steering experiments.

## ADDED Requirements

### Requirement: Executable paired evaluation
A configured evaluation SHALL execute base and steered arms on identical prompts with identical model, template, decoding, context and budgets, differing only by the declared intervention. It SHALL preserve every attempted prompt's raw result and status. An invocation that executes no examples SHALL NOT report successful validation.

#### Scenario: Different temperature is not a valid pair
- **WHEN** one arm contains a conflicting temperature or another undeclared non-steering option
- **THEN** the runner rejects the pair before measuring it

#### Scenario: Real residual arm
- **WHEN** a V4.1 residual vector and scale are selected
- **THEN** the steered arm invokes that active site and does not silently use an inactive FFN/attention site

### Requirement: Numerical and benign first pass
The default evaluation profile SHALL run declared numerical/no-op checks and benign tasks and return KPIs without requiring an LLM judge. It SHALL identify its measured coverage and optional unmeasured diagnostics. A first-token screen SHALL remain separately selectable. The first pass SHALL NOT automatically escalate to a broader benchmark after success or failure.

#### Scenario: No semantic grader available
- **WHEN** the declared numerical/benign profile does not require an LLM judge
- **THEN** it can return its deterministic KPIs without that judge
- **AND** unavailable semantic metrics remain explicitly unmeasured rather than guessed

#### Scenario: Broader benchmark is a separate request
- **WHEN** the first pass produces promising or inconclusive KPIs
- **THEN** no broader suite is launched without explicit selection and launch scope

### Requirement: Run and evidence identity
Each run SHALL record model/build identity, effective intervention, vector content, data selection, decoding, scorer identity, seeds and cache policy. Raw results and the report SHALL reference that manifest. Results from different identities SHALL NOT be reused as the same experiment.

#### Scenario: Vector changed in place
- **WHEN** the same vector path contains different bytes in a later run
- **THEN** the later run has a different identity and cannot reuse prior acceptance evidence

### Requirement: Explicit execution failures
Timeouts, nonzero child exits, empty or malformed outputs, missing records and incomplete required phases SHALL be reported explicitly. They SHALL NOT become semantic labels, zero divergence or silently dropped examples. A requested validation with such failures SHALL exit nonzero after preserving partial evidence.

#### Scenario: Thinking budget exhausted
- **WHEN** generation ends before producing a final answer because its budget expires in reasoning
- **THEN** the result is incomplete rather than automatically classified as refusal

### Requirement: Distinct refusal and launch outcomes
A refusal by the tested model SHALL remain a measured response when validly scored. A grader refusal SHALL be an invalid or missing grade with its own count, not a model-response label. A blocked or unperformed launch SHALL NOT create evaluated examples or a benchmark verdict. These outcomes SHALL remain visible in KPI summaries.

#### Scenario: Judge declines to classify
- **WHEN** a grader refuses to evaluate a response
- **THEN** the summary records a grading failure and does not increase the tested model's refusal or compliance count

#### Scenario: Agent cannot launch the evaluation
- **WHEN** orchestration does not permit a requested run
- **THEN** no measurement is claimed and an operator-run path can be offered without weakening the evaluation's controls or launch requirements

### Requirement: KPI-only default presentation
Default terminal output and summary files SHALL contain only allowlisted KPI/status fields, experiment identities, counts, uncertainty and opaque evidence references. Prompt/response text, token strings, judge narratives, text-bearing arguments and raw child errors SHALL stay in local evidence. Failure paths SHALL obey the same presentation boundary.

#### Scenario: Child error contains a prompt
- **WHEN** a subprocess or scorer error echoes input content
- **THEN** the default stdout, stderr and summary expose its structured status/reference without reproducing that content

### Requirement: Explicit audit and stored-result rendering
Raw evidence SHALL remain available through explicitly requested audit. Measurement scope and report visibility SHALL be independent; changing presentation SHALL NOT change scores, denominators or verdicts. Rendering a stored run SHALL NOT launch generation or grading, fill missing scores or upgrade its acceptance status.

#### Scenario: Operator-run batch consumed offline
- **WHEN** an agent renders KPIs from an identified stored run
- **THEN** no model or judge runs and the original coverage and failures remain visible

#### Scenario: Audit has the same numbers
- **WHEN** the same stored run is rendered as KPIs and as an explicit audit
- **THEN** both views agree on metrics, denominators and verdicts while only audit reveals selected raw evidence

### Requirement: No-op and perturbation controls
The runner SHALL compare baseline with explicit zero scale and zero direction at nonzero scale, checking record identity and output before labels. Failed no-op controls SHALL stop validation. Random-direction controls SHALL report seed, mask and matching method; their behavioral effects SHALL limit specificity claims rather than automatically prove a harness bug.

#### Scenario: Same labels with different outputs
- **WHEN** a no-op arm changes tokens or completion text but preserves labels
- **THEN** the no-op control fails

#### Scenario: Random direction has an effect
- **WHEN** a random control materially changes the measured behavior
- **THEN** the report flags direction-specificity evidence as unresolved and preserves the measurements

### Requirement: Diagnostic first-token screen
A first-token screen SHALL retain token IDs, lexicon version and probability support in its evidence. Its default KPI view SHALL report numeric aggregates and support without raw token strings or completions. A top-k lexicon mass SHALL be labeled a lower bound. The screen SHALL NOT establish completed-response efficacy or automatically reject a candidate with an unchanged first-token metric.

#### Scenario: Unchanged opener
- **WHEN** a candidate leaves the initial lexicon mass unchanged
- **THEN** it remains eligible for a separately requested complete-response evaluation

### Requirement: Five-axis complete evaluation
Full A-E acceptance SHALL require A response behavior, B benign fidelity, C over-refusal, D capability and E domain breadth. A SHALL show keyword, three-way judge and calibrated StrongREJECT or explicitly named variant scores separately. Completing a narrower selected profile SHALL NOT imply full A-E acceptance; missing required axes SHALL remain unmeasured.

#### Scenario: Minimum milestone only
- **WHEN** only the minimum text protocol or screen has run
- **THEN** the report names its coverage and does not claim complete A-E acceptance

### Requirement: Calibrated fixed graders
Grader acceptance SHALL use fixed independently annotated responses and record the rubric/model identity. The grader SHALL remain unsteered across compared arms. Invalid grader output SHALL be marked invalid, not converted to a middle class. Benchmark variants SHALL be named rather than presented as exact published scorers.

#### Scenario: Unknown label
- **WHEN** the grader returns text outside the declared label/schema contract
- **THEN** parsing reports an invalid grade and does not substitute DEFLECT

### Requirement: Forced-prefix distribution comparison
A reported full KL SHALL use the complete shared vocabulary and identical forced-token prefixes in both arms. Token IDs, lengths and sequence identities SHALL match. Empty, nonfinite or mismatched data SHALL fail. Independently normalized top-k lists or divergent generated continuations SHALL NOT be reported as full forced-prefix KL.

#### Scenario: Near-tied top tokens
- **WHEN** two nearly identical distributions exchange their top token
- **THEN** the full KL remains near zero and top-k support changes do not create an artificial large full-KL result

#### Scenario: Missing sequence
- **WHEN** a distribution sequence is empty or shorter than its paired sequence
- **THEN** evaluation fails instead of returning zero or truncating to the shorter sequence

### Requirement: Relevant fidelity controls
Fidelity evidence SHALL include same-build base/base and scale-zero controls. A noise floor from another quantization or intervention protocol SHALL NOT be used as the acceptance threshold for the current run without reproducing that comparison. Exploratory proxies SHALL NOT pass the full fidelity gate.

#### Scenario: External requantization floor
- **WHEN** a published requantization experiment reports a nonzero KL floor
- **THEN** a same-GGUF runtime-steering report identifies it only as external reference unless the same comparison is executed

### Requirement: Capability and modality identity
Capability runs SHALL measure both actual interventions and identify the cases/subjects evaluated. Image and thinking repeats SHALL be separate paired protocols with verified input delivery and completion. A generic suite name or non-empty image response SHALL NOT establish benchmark or vision coverage.

#### Scenario: Image really reaches vision
- **WHEN** a rendered benign prompt is used to validate the image runner
- **THEN** the model receives a supported image payload through the vision component and the test checks that its content was read

#### Scenario: Over-refusal subset
- **WHEN** only part of the pinned XSTest-safe set is evaluated
- **THEN** the exact selector and count are reported and the result is not called the full set

### Requirement: Paired decisions and holdout separation
Acceptance SHALL use a predeclared primary metric, prompt-paired uncertainty and explicit non-inferiority margins for quality guards. Without margins the run SHALL be report-only. An inconclusive difference SHALL NOT be called equivalence. Tuning and held-out evaluation SHALL remain separate.

#### Scenario: Confidence interval crosses zero
- **WHEN** a guard's interval does not establish the declared non-inferiority bound
- **THEN** the report marks acceptance unresolved rather than inferring no degradation

### Requirement: Reusable verified steering report contract
The runner SHALL expose a versioned KPI/report contract with profile coverage, metric denominators and evidence identities. Reuse for future steering proposals SHALL be qualified on distinct experiment configurations without forking the runner. Qualification SHALL identify the verified profile/version; it SHALL NOT transfer acceptance to a new intervention or an unmeasured axis.

#### Scenario: Reuse for a later layer-mask proposal
- **WHEN** the runner has been verified on scale and layer-mask comparisons and a later steering proposal uses the qualified profile
- **THEN** that proposal can reuse execution, controls and reporting with its own pinned intervention, split and acceptance criteria
- **AND** its new intervention still requires its own correctness and outcome evidence

#### Scenario: Only benign coverage has been qualified
- **WHEN** the numerical/benign profile is verified but the full benchmark is not
- **THEN** the reusable contract advertises only that verified coverage and does not claim full-benchmark qualification

### Requirement: Separate external reproduction
Published intervention reproduction SHALL require the identified model artifact, prompts, intervention, decoding and grader protocol. Unavailable prerequisites SHALL be named and reproduction marked unavailable. Its figures SHALL remain separate from local experiments; a local mismatch alone SHALL NOT be diagnosed as a harness bug.

#### Scenario: Different application hook
- **WHEN** the local runtime applies a weighted-fold edit while the publication used another hook
- **THEN** the local result is labeled a different intervention, not a failed exact reproduction
