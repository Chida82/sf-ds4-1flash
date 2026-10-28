# Spec Delta

## ADDED Requirements

### Requirement: Approximate decoder prefill is opt-in
The CLI, the server and the benchmark SHALL accept `--approx-decoder-prefill`, off by default. Without it, prefill SHALL produce bitwise the same KV state, Engram history, logits and tokens as the build before the flag existed. This flag is the only sanctioned exception to identical output, and the exception SHALL be stated in the model notes, the README and this specification.

#### Scenario: Flag absent
- **WHEN** the parity oracle, the test suite and the harness run without the flag
- **THEN** they pass bitwise against the previous build

### Requirement: What the approximate mode computes
With the flag, each batched prefill sweep SHALL run layers 0 to 20 as without the flag, so layer 20 publishes the decoder layers' compressed KV for every row. It SHALL run layers 21 to 39 only on the sweep's last 128 rows, each row attending in the sliding window only to keys from the first of those rows onward. Token-by-token prefill tails and decode SHALL be unchanged.

#### Scenario: Cold prompt with the flag
- **WHEN** a 10000-token prompt is prefilled with the flag
- **THEN** generation succeeds, the decoder layers report 128 rows per sweep in the prefill profile, and the time to first token is reported beside the run without the flag

#### Scenario: First token may change
- **WHEN** the same greedy prompt runs with and without the flag
- **THEN** the outputs may differ from the first generated token on, and the harness reports the first differing position rather than failing

### Requirement: Approximate state does not persist
A session prefilled with the flag SHALL refuse session payload saves and loads and snapshots, with a message naming the flag. A server started with the flag SHALL NOT open its disk KV cache, SHALL say so once, and SHALL leave existing entries untouched.

#### Scenario: Server with a disk cache directory
- **WHEN** the server starts with `--approx-decoder-prefill --kv-disk-dir DIR`
- **THEN** it logs that the disk cache is not used with the flag, and nothing under DIR is read or written

#### Scenario: Snapshot request
- **WHEN** a client asks a session prefilled with the flag to save its state
- **THEN** the request fails with a message naming the flag, and no file is written

### Requirement: Not combined with steering
The engine SHALL refuse to start when the flag and directional steering, a nonzero residual scale or a steering profile, are both requested, naming both.

#### Scenario: Flag with a steering profile
- **WHEN** the CLI starts with `--approx-decoder-prefill --steering-profile sf-ds4-1flash-candor`
- **THEN** it exits before loading weights, naming both options
