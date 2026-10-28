# Spec Delta

## Purpose

Capture the V4.1 attention-input fold of individual prompts at the refusal-decision
position, with enough identity to be re-analysed later, and compute from those
captures the offline analyses that decide, before any model time is spent, which
steering operator families are worth testing.

## ADDED Requirements

### Requirement: Per-prompt fold capture with identity
The capture tool SHALL record, for every prompt in its manifest, the unsteered
attention-input fold of the last prompt token at every model layer, as one file of
40 rows by 5120 little-endian f32 values (row 0 is layer 0) taken before that
layer's own steering edit, and SHALL write a manifest naming each prompt's dataset
index, class labels, text hash, the server's steering identity, the run identifier
and the file hash. It SHALL request at most one token per prompt.

#### Scenario: One prompt, one file
- **WHEN** the capture runs a prompt whose prefill spans one or more chunks
- **THEN** exactly the last 40 rows of the dump are stored for it, the file is
  819200 bytes, and the manifest entry carries its class, index, text hash, steering
  identity and file hash

#### Scenario: Malformed dump
- **WHEN** the dump after a request holds a row count that is not a positive multiple of 40
- **THEN** the tool records an error naming that prompt, stores no file for it,
  never truncates silently, and continues

#### Scenario: Steered capture is labelled
- **WHEN** the capture server runs with a steering file and nonzero scale
- **THEN** every manifest entry names that file hash and scale, and the stored rows
  are the pre-edit fold of each layer under the steered upstream layers

#### Scenario: Explicitly listed prompts
- **WHEN** an index is listed under an explicit class (floor, target) and already
  belongs to another class
- **THEN** its rows are stored once and the manifest carries both labels

### Requirement: Pre-registered offline gates
The analysis SHALL compute from a capture, per layer and without a model, the
separation of resistant versus opened prompts in the plane of the first two
reference directions and in the orthonormalised span of all of them, and the
detector coordinate's ROC area in cosine units against opened and against benign
prompts. Decision rules SHALL be written in the measurements log before the
capture runs, and the output SHALL state each rule's outcome next to its number.

#### Scenario: Rule outcome is explicit
- **WHEN** the analysis finishes
- **THEN** its report lists each pre-registered rule, the per-layer values it uses,
  and a supported, rejected or inconclusive verdict for the arm it gates

#### Scenario: Detector threshold and layer proposed
- **WHEN** the detector threshold is set at the lowest floor-prompt coordinate of a
  layer
- **THEN** the report gives, for that layer, the benign false-positive rate and the
  resistant recall at it, and names the threshold and layer the detector rule
  proposes

#### Scenario: Span and per-prompt coordinates
- **WHEN** three or more reference directions are loaded
- **THEN** the report gives every prompt's coordinates in the orthonormalised span
  and its cosine to each reference direction, and names the prompts listed as
  targets so that a class of two stays visible

#### Scenario: Synthetic self-check
- **WHEN** the analysis runs its self-check on generated classes with a planted
  separating direction and a planted offset in the span
- **THEN** it reports an AUC near one along the planted direction and near one half
  along a random one, recovers the planted offset in the span separation, and the
  self-check exits nonzero otherwise

### Requirement: Native direction derivation with provenance
A direction derived from a capture SHALL be the per-layer unit difference of class
means in the existing 40x5120 f32 format with row 0 zero, with a sidecar recording
the capture run, the class definitions and sizes, each layer's raw difference norm,
its cosine to every reference direction and the file hash. Derivation SHALL be
deterministic for a given capture and SHALL launch no model.

#### Scenario: Deterministic derivation
- **WHEN** the derivation runs twice on the same capture
- **THEN** the emitted files have identical hashes and sidecars

#### Scenario: Planted direction recovered
- **WHEN** the self-check plants a direction into synthetic class means
- **THEN** the derived unit direction has cosine above 0.99 to it, and the first
  principal component of the planted spread has cosine above 0.99 to its axis

#### Scenario: Principal components
- **WHEN** a principal-component basis is requested from the same capture
- **THEN** its components are orthonormal per layer, emitted as separate direction
  files the existing slots can apply, with each component's explained-variance
  share in the sidecar

### Requirement: Vector masking by layer
A masking tool SHALL produce from a valid direction file a copy whose selected rows
are zero, selecting rows either by an explicit layer list or by a per-layer cosine
threshold against a second direction file, leaving every other row byte-identical.
It SHALL write a sidecar naming the source hash, the rule, the zeroed layers and
the output hash, and the output SHALL pass the engine's direction validation.

#### Scenario: Rows zeroed, others untouched
- **WHEN** layers 9-39 are selected
- **THEN** those rows are zero, rows 1-8 equal the source bytes, and the engine
  accepts the file

#### Scenario: Cosine rule
- **WHEN** the rule is "zero where |cos| to the reference exceeds 0.4"
- **THEN** exactly the layers whose per-layer |cos| exceeds 0.4 are zeroed and the
  sidecar lists them with their cosines

### Requirement: Composition geometry report
A model-less tool SHALL compute, for two unit directions at a given cosine and two
scales, the in-plane 2x2 operator of their sequential folds and of their additive
sum: the coefficient left on the first direction's component, the eigenvalues or
rotation angle and amplification, and the operator norm against the larger single
fold. It SHALL reproduce the reference cases in its self-check.

#### Scenario: Reference case
- **WHEN** the tool runs with cosine 0.72 and scales 5 and 6
- **THEN** it prints coefficient +8.44, rotation 87.9 degrees, amplification 4.47
  and norm 15.0 for the sequential form, eigenvalues -8.48 and -0.52 for the
  additive form, each within 0.01, and the self-check passes

#### Scenario: Dose cases
- **WHEN** the tool runs with cosine 0.22 at scales 7 and 6, 7 and 2, 7 and 3, and
  5 and 4, with cosine 0 at 5 and 6, and with cosine 0.5 at 1 and 1
- **THEN** it prints norms 9.58, 6.00, 6.45, 5.01, 5.00 and 0.50 within 0.01, and
  flags only the pairs whose norm exceeds the larger single fold by more than 20%
