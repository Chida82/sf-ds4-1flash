# Spec Delta

## ADDED Requirements

### Requirement: Splicing a separately encoded segment is measured against the joint encoding
A tool on the public API SHALL copy one segment's compressed rows and index
keys, at unchanged positions, into a snapshot whose corresponding positions
were encoded as filler, rewrite the token ids, prove the session accepted the
spliced prefix, and compare the decision with the jointly encoded state and
with the filler state.

#### Scenario: The splice is real
- **WHEN** the spliced snapshot is loaded and the question suffix is synced
- **THEN** the common prefix equals the spliced length and only the suffix is evaluated

#### Scenario: Offsets are right
- **WHEN** the layer-2 rows of positions more than 254 tokens into the second segment are compared between the joint and the filler snapshots
- **THEN** they are bitwise equal

#### Scenario: Recorded result
- **WHEN** the run finishes
- **THEN** the record holds agreement, KL and legal mass for spliced, filler and the schedule noise floor, by item kind, and the gate's outcome

### Requirement: Composed state never reaches the chat's stores
A spliced snapshot SHALL NOT be written to the disk KV store or to the state
cache of `830`.

#### Scenario: Isolation of the experiment
- **WHEN** the tool exits
- **THEN** no file outside the work directory has been written
