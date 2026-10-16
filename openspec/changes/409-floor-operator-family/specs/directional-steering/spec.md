# Spec Delta

## ADDED Requirements

### Requirement: Composition geometry reported at engine open
When two residual steering directions are active, the engine SHALL print at open
the median per-layer absolute cosine between them over the layers where both are
nonzero, and SHALL warn in one line that the two folds do not commute and compose
as a rotation when that median exceeds 0.2 and either scale exceeds 2. The report
SHALL change no computation. A single active direction SHALL print nothing new.

#### Scenario: Interfering pair named
- **WHEN** the first direction is msuiche at scale 5 and the second is the
  abliteration vector at scale 6
- **THEN** the open log states a median |cos| of about 0.72 and the warning line

#### Scenario: Orthogonal pair silent
- **WHEN** the second direction is the per-layer orthogonal residual of the first
- **THEN** the open log states a median |cos| near 0 and no warning

### Requirement: Gated selection between the two residual slots
With a gate direction file and a gate threshold in cosine units, every row at the
fold SHALL compute the cosine between the gate direction of that layer and the
row, SHALL apply only the second slot's fold when the cosine is at or above the
threshold, and only the first slot's fold otherwise. The two slots SHALL never
both apply to one row while the gate is active. The gate file SHALL pass the same
validation as a direction file, a gate SHALL require both slots to be active, and a
zero gate row SHALL select the first slot for that layer. The gate SHALL apply on
every route that produces an attention input, with the same rounding order as the
ungated fold. Without a gate file the behaviour SHALL be bitwise the current one.

#### Scenario: Never fires
- **WHEN** the threshold is above 1
- **THEN** the output equals, bitwise, a run with the first slot alone

#### Scenario: Always fires
- **WHEN** the threshold is below -1
- **THEN** the output equals, bitwise, a run with the second slot alone

#### Scenario: Mixed batch
- **WHEN** a prefill batch holds rows on both sides of the threshold
- **THEN** each row receives exactly one slot's fold, and the result agrees with the
  CPU reference to the documented tolerance

#### Scenario: Gate without a slot
- **WHEN** a gate file is given and either slot's scale is zero
- **THEN** engine open fails with an error naming the missing slot

### Requirement: Target fold in cosine units
Each residual slot SHALL accept a target in cosine units. With a target `tau`, the
fold SHALL subtract `F * (dot(d,h) - tau * |h|) * d` so that the row's coordinate
along `d` is set toward `tau * |h|` rather than scaled; with `tau = 0` the fold
SHALL be bitwise the current `F * dot(d,h) * d`. The target SHALL be finite and
within [-1, 1], SHALL apply on every route with the same rounding order, and SHALL
be refused when the slot's scale is zero.

#### Scenario: Zero target is the current fold
- **WHEN** a target of 0 is given with any scale
- **THEN** logits, KV state and Engram history are bitwise those of the same run
  without the target option

#### Scenario: Coordinate set, not scaled
- **WHEN** a unit direction, scale 1 and target `tau` are applied to a row
- **THEN** the row's cosine to the direction after the fold equals `tau` within the
  documented tolerance, for rows of different norms

#### Scenario: Invalid target
- **WHEN** the target is non-finite or outside [-1, 1]
- **THEN** engine open fails with an error naming the option

### Requirement: Residual-write projection site
With a write-site direction file and a nonzero write scale, the engine SHALL
subtract `W * dot(r[L], out) * r[L]` from the attention output and from the MoE
output of layers 1-39 before each enters the residual streams, on every route
(decode, batch prefill, the reconstructed rows of the wide-sweep decoder suffix,
and both tensor-parallel ranks). The site SHALL have its own name and revision
printed at open. It SHALL default to off and SHALL be bitwise the current engine
when off, including when the file is present with scale zero. While active it
SHALL be subject to the same persistent-state refusals as the fold, and the
existing attention and FFN legacy options SHALL remain refused on V4.1.

#### Scenario: Off path bitwise
- **WHEN** a write-site file is given with write scale 0
- **THEN** logits, KV state and Engram history are bitwise the unsteered run

#### Scenario: Both writes projected on every route
- **WHEN** a unit direction is active at write scale 1
- **THEN** a route test shows the attention and MoE writes of each layer with no
  component along the direction, on decode, batch and reconstructed rows alike

#### Scenario: Composes with the fold
- **WHEN** the write site is active together with a fold direction
- **THEN** both apply, the fold after the layer's input is formed, and the route
  test agrees with the CPU reference

### Requirement: Experimental operator non-adoption
Every operator option this change adds SHALL be tied to a pre-registered decision
rule in the measurements log. An operator whose rule ends rejected or inconclusive
SHALL be removed from the engine, the frontends, the environment registry, the
tests and the documentation before the change is archived, and its measured
outcome SHALL remain recorded. No experimental operator SHALL become a default.

#### Scenario: Rejected arm leaves no flag
- **WHEN** an arm's rule ends rejected
- **THEN** its flags are absent from `--help`, its names are absent from the
  environment registry and the help text, and the measurements log holds its block

#### Scenario: Supported arm stays opt-in
- **WHEN** an arm's rule ends supported
- **THEN** its options remain off by default and under the existing V4.1 steering
  opt-in
