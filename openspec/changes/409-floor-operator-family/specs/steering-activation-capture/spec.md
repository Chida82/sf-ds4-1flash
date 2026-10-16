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
40 rows by 5120 little-endian f32 values (row 0 is layer 0), taken before that
layer's own steering edit. It SHALL write a manifest naming for each prompt its
dataset index, class label, prompt text hash, the server's steering identity
(none, or file hash and scales), the run identifier and the capture file's hash.
The tool SHALL request one token at most per prompt and SHALL generate no text
beyond that. A dump whose row count is not a positive multiple of 40 SHALL be
rejected for that prompt with an error naming the prompt, never truncated silently.

#### Scenario: One prompt, one file
- **WHEN** the capture runs a prompt whose prefill spans one or more chunks
- **THEN** exactly the last 40 rows of the dump are stored for it, the file is
  819200 bytes, and the manifest entry carries its class, index, text hash, steering
  identity and file hash

#### Scenario: Malformed dump
- **WHEN** the dump after a request holds a row count that is not a positive multiple of 40
- **THEN** the tool records an error for that prompt, stores no file for it and continues

#### Scenario: Steered capture is labelled
- **WHEN** the capture server runs with a steering file and nonzero scale
- **THEN** every manifest entry names that file hash and scale, and the stored rows
  are the pre-edit fold of each layer under the steered upstream layers

### Requirement: Pre-registered offline gates
The analysis SHALL compute from a capture, per layer and without launching a
model: the two-class separation of resistant versus opened prompts inside the
plane spanned by the two reference directions and along the detector direction;
the area under the ROC curve of the detector coordinate, in cosine units, for
resistant versus opened and resistant versus benign, with the benign false-positive
rate at the threshold that classifies every floor prompt as resistant; and the
threshold and layer that rule proposes. Decision rules for every operator family
SHALL be written in the measurements log before the capture that feeds them is
run, and the analysis output SHALL state each rule's outcome next to the number it
was computed from.

#### Scenario: Rule outcome is explicit
- **WHEN** the analysis finishes
- **THEN** its report lists each pre-registered rule, the per-layer values it uses,
  and a supported, rejected or inconclusive verdict for the arm it gates

#### Scenario: Synthetic self-check
- **WHEN** the analysis runs its self-check on generated classes with a planted
  separating direction
- **THEN** it reports an AUC near one along the planted direction and near one half
  along a random one, and the self-check exits nonzero otherwise

### Requirement: Native direction derivation with provenance
A direction derived from a capture SHALL be the per-layer unit difference of class
means in the existing 40x5120 f32 format with row 0 zero, and SHALL carry a sidecar
recording the capture run, the class definitions and sizes, each layer's raw
difference norm, its cosine to every reference direction, and the file hash. A
principal-component basis derived from the same capture SHALL be orthonormal per
layer, SHALL record each component's explained variance share, and SHALL be
emitted as separate direction files so the existing slots can apply it. Derivation
SHALL be deterministic for a given capture and SHALL launch no model.

#### Scenario: Deterministic derivation
- **WHEN** the derivation runs twice on the same capture
- **THEN** the emitted files have identical hashes and sidecars

#### Scenario: Planted direction recovered
- **WHEN** the self-check plants a direction into synthetic class means
- **THEN** the derived unit direction has cosine above 0.99 to it, and the first
  principal component of the planted spread has cosine above 0.99 to its axis

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
rotation angle and amplification, and SHALL reproduce the reference case
(cos 0.72, scales 5 and 6: coefficient +8.44, rotation 87.9 degrees, amplification
4.47; additive eigenvalues -8.48 and -0.52) in its self-check.

#### Scenario: Reference case
- **WHEN** the tool runs with cosine 0.72 and scales 5 and 6
- **THEN** it prints the four reference values within 0.01 and the self-check passes
