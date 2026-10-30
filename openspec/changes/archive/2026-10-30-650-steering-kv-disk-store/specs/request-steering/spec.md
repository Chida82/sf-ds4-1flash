# Spec Delta

## ADDED Requirements

### Requirement: Disk cache with a profile loaded
A server started with `--kv-disk-dir` SHALL open its disk KV cache whether or not a steering profile is loaded. Unsteered requests SHALL use the cache root exactly as a server without a profile does.

#### Scenario: Unsteered requests keep their cache
- **WHEN** a server with the profile and `--kv-disk-dir` answers the same long unsteered request twice
- **THEN** the second request loads the entry the first stored under the cache root, and its tokens equal the first's

### Requirement: Steered requests use their own store
Steered requests SHALL look up, load, store and evict only under the `steering` subdirectory of the cache root, and unsteered requests only in the root itself. Neither SHALL read, write or delete an entry of the other.

#### Scenario: Steered entry stays in its folder
- **WHEN** a steered request stores a prefix and the same steered request is repeated
- **THEN** the entry file is under `<root>/steering/`, the repeat loads it, and its tokens equal the first response's

#### Scenario: No cross reads
- **WHEN** the same prompt is sent first unsteered and then steered on a fresh server
- **THEN** the steered request finds no entry and evaluates its whole prompt, and no file in the root changes because of it

#### Scenario: The root store ignores the subfolder
- **WHEN** the root store lists its entries
- **THEN** no file under `<root>/steering/` is among them

### Requirement: Steering store bound to the profile's bytes
The steering store SHALL record the SHA-1 of the loaded profile file in `<root>/steering/PROFILE`. At startup, if the recorded identity differs, or is missing while entries exist, the server SHALL delete only the entry files in `<root>/steering/` before serving, log how many, and record the new identity.

#### Scenario: Same profile keeps its entries
- **WHEN** the server restarts with a byte-identical profile
- **THEN** every entry under `<root>/steering/` is kept and can be loaded

#### Scenario: Changed profile empties only its store
- **WHEN** the server restarts with a profile whose bytes differ, even under the same name
- **THEN** every `<40 hex>.kv` file in `<root>/steering/` is deleted, files in the root and non-entry files in `<root>/steering/` are untouched, and the log states the count

#### Scenario: Missing identity with entries
- **WHEN** `<root>/steering/` holds entry files but no `PROFILE`
- **THEN** the entries are deleted as for a changed profile and the identity is recorded

### Requirement: One budget per store
Each of the two stores SHALL apply the configured disk budget on its own, with the existing eviction order, so the cache can occupy up to twice the configured budget.

#### Scenario: Eviction stays inside a store
- **WHEN** the steering store exceeds the budget
- **THEN** entries are evicted only from `<root>/steering/`, by the existing eviction score, and no root entry is removed
