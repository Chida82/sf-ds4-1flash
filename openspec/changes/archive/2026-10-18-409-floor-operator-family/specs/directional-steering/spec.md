# Spec Delta

## ADDED Requirements

### Requirement: Composition geometry reported at engine open
When two residual steering directions are active, the engine SHALL print at open
the median per-layer absolute cosine between them over the layers where both are
nonzero, and the norm of the in-plane operator of the two sequential folds built
from that median and the two scales. It SHALL warn in one line when that norm
exceeds the larger single fold by more than 20%. The report SHALL change no
computation. A single active direction SHALL print nothing new.

#### Scenario: Interfering pair named
- **WHEN** the first direction is msuiche at scale 5 and the second is the
  abliteration vector at scale 6
- **THEN** the open log states a median |cos| of about 0.72, a composed norm of
  about 15 against a single fold of 5, and the warning line

#### Scenario: Over-dosed pair named
- **WHEN** the two directions have median |cos| 0.22 and the scales are 7 and 6
- **THEN** the open log states a composed norm of about 9.6 against a single fold
  of 6, and the warning line

#### Scenario: Orthogonal pair silent
- **WHEN** the second direction is the per-layer orthogonal residual of the first,
  at scales 5 and 6
- **THEN** the open log states a median |cos| near 0 and a composed norm equal to
  the larger single fold, and no warning

### Requirement: Gated selection between the two residual slots
With a gate direction file and a gate threshold in cosine units, every row at the
fold SHALL receive exactly one slot's fold: the second slot's when the row's cosine
to that layer's gate direction is at or above the threshold, the first slot's
otherwise. The gate SHALL apply on every route that produces an attention input,
with the same rounding order as the ungated fold. Without a gate file the
behaviour SHALL be bitwise the current one.

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

#### Scenario: Zero gate row
- **WHEN** the gate file's row for a layer is zero
- **THEN** every row of that layer receives the first slot's fold

#### Scenario: Gate file validated like a direction
- **WHEN** the gate file fails the direction-file validation
- **THEN** engine open fails with the same error as for a direction file

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

#### Scenario: Two targets bound the dose
- **WHEN** both slots run at scale 1 with targets `tau1` and `tau2`
- **THEN** the row's coordinates along the two directions after the folds are
  `tau1 * |h|` and `tau2 * |h|` within the documented tolerance, whatever the
  coordinates were before

#### Scenario: Invalid target
- **WHEN** the target is non-finite or outside [-1, 1]
- **THEN** engine open fails with an error naming the option

### Requirement: Residual-write projection site
With a write-site direction file and a nonzero write scale, the engine SHALL
subtract `W * dot(r[L], out) * r[L]` from the attention output and from the MoE
output of each layer before they enter the residual streams, on every route; the
MoE output SHALL take a separate direction file when one is given, and either site
file SHALL be accepted alone. The site SHALL have its own name and revision printed at open, SHALL default to off
and SHALL be bitwise the current engine when off.

#### Scenario: Off path bitwise
- **WHEN** a write-site file is given with write scale 0
- **THEN** logits, KV state and Engram history are bitwise the unsteered run

#### Scenario: Both writes projected on every route
- **WHEN** a unit direction is active at write scale 1
- **THEN** a route test shows the attention and MoE writes of each layer with no
  component along the direction, on decode, batch and reconstructed rows alike,
  and on both tensor-parallel ranks

#### Scenario: Per-site directions
- **WHEN** a MoE write-site file is given alongside the attention file
- **THEN** the attention write of each layer has no component along the attention
  file's row and the MoE write none along the MoE file's row, each keeping its
  component along the other, on every route

#### Scenario: MoE write alone
- **WHEN** only a MoE write-site file is given with a nonzero write scale
- **THEN** the MoE write is projected, the attention write is bitwise untouched,
  and the run counts as write-site active for the persistence guards

#### Scenario: Composes with the fold
- **WHEN** the write site is active together with a fold direction
- **THEN** both apply, the fold after the layer's input is formed, and the route
  test agrees with the CPU reference

#### Scenario: Persistent state refused while active
- **WHEN** the write scale is nonzero
- **THEN** payloads and snapshots are refused and the server skips its KV disk
  directory, as for the fold, and the legacy attention and FFN options stay
  refused on V4.1

#### Scenario: Two write directions
- **WHEN** a second write-site file is given
- **THEN** both projections apply in order on every route, the result agrees with
  the CPU reference, and at scale 1 the in-plane norm of the composition equals
  the pair's median |cos|, below 1

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

#### Scenario: Rule names its metre and path
- **WHEN** a rule is pre-registered
- **THEN** it names the high-water mark of the arm's vector family it is measured
  against (full-set count, selector, tokens, judge) and the generation path, a
  subset result is re-projected onto the full set before comparison, and a new
  vector or site is confirmed on the full set, never by carry-forward
