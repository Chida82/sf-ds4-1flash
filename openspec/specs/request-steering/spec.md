# request-steering Specification

## Purpose
Lets the server keep one steering profile loaded but off, lets each request turn it on through its model id, and keeps the state computed by steered and unsteered requests from ever mixing.

## Requirements

### Requirement: Profile loaded on request
The server SHALL accept `--steering-profile-on-request NAME|FILE`, resolving the profile as the CLI does. With it, the server SHALL load the profile and run every request unsteered unless the request selects steering.

#### Scenario: A request without steering is the plain model
- **WHEN** a server started with the shipped profile answers a greedy request for `deepseek-v4.1-flash`
- **THEN** the response's tokens equal those of a server started without any profile, for the same request

#### Scenario: Unknown profile
- **WHEN** the server is started with a name that matches no profile and no readable file
- **THEN** it refuses to start and lists the profiles that exist

### Requirement: Server rejects the CLI flag
The server SHALL refuse to start when given `--steering-profile`, with a message that names `--steering-profile-on-request` and says that steering is then selected per request.

#### Scenario: Old command line
- **WHEN** the server is started with `--steering-profile sf-ds4-1flash-candor`
- **THEN** it exits with a nonzero status before loading the model, and its message names `--steering-profile-on-request`

### Requirement: Steering selected by model id
A request SHALL be steered when its model id is a known model id followed by `-steering`: `deepseek-v4.1-flash-steering`, `deepseek-chat-steering` or `deepseek-reasoner-steering`. The id without the suffix SHALL keep its thinking semantics.

#### Scenario: Steered request equals the always-on server
- **WHEN** a greedy request for `deepseek-v4.1-flash-steering` is answered at a given effort level
- **THEN** its tokens equal those the server before this change, started with `--steering-profile` and the same profile, produced for the same request sent as `deepseek-v4.1-flash`

#### Scenario: Chat alias with the suffix
- **WHEN** a request for `deepseek-chat-steering` sends no thinking control
- **THEN** it is steered and thinking is off

#### Scenario: Explicit thinking control still wins
- **WHEN** a request for `deepseek-chat-steering` sends `thinking: true`
- **THEN** it is steered and thinking is on

#### Scenario: Response names the requested id
- **WHEN** a request for `deepseek-v4.1-flash-steering` is answered
- **THEN** the response's `model` field is `deepseek-v4.1-flash-steering`

### Requirement: Steering request without a profile
A request whose model id ends in `-steering` SHALL be answered with HTTP 400 and evaluated not at all when the server has no profile loaded, or when the id before the suffix is not a known model id.

#### Scenario: Server without a profile
- **WHEN** a server started without `--steering-profile-on-request` receives a request for `deepseek-v4.1-flash-steering`
- **THEN** it answers 400 with a message naming `--steering-profile-on-request`

#### Scenario: Unknown base id
- **WHEN** a server with a profile receives a request for `foo-steering`
- **THEN** it answers 400 naming the known model ids

### Requirement: Steering ids in the model list
`/v1/models` SHALL list `deepseek-v4.1-flash-steering` beside `deepseek-v4.1-flash` when a profile is loaded, and SHALL NOT list it otherwise. `/v1/models/<id>` SHALL resolve a `-steering` id only when a profile is loaded.

#### Scenario: Listing with and without a profile
- **WHEN** `/v1/models` is requested from a server with a profile and from one without
- **THEN** the first lists both ids and the second lists only `deepseek-v4.1-flash`

### Requirement: No live state crosses steering
The server SHALL NOT extend, restore or replay, for a request, any live state computed under the other steering setting: slot prefixes, checkpoints, continued prefixes or tool replay state. When choosing a slot it SHALL treat such state as reusing nothing.

#### Scenario: Alternating requests on one slot
- **WHEN** a one-slot server answers a request for a prompt unsteered, then the same prompt with `-steering`, then unsteered again
- **THEN** each of the three requests evaluates its whole prompt, and the third response's tokens equal the first's

#### Scenario: Routing prefers a matching slot
- **WHEN** a server with two slots holds the same prefix once unsteered and once steered, and a steered request extends that prefix
- **THEN** the request is routed to the steered slot and reuses its prefix

### Requirement: No per-request steering with tensor parallelism
The server SHALL refuse to start with `--steering-profile-on-request` when it runs as a tensor-parallel or distributed leader or worker, since the per-request setting is not carried to other ranks.

#### Scenario: TP leader with a profile
- **WHEN** the server is started as a TP leader with `--steering-profile-on-request`
- **THEN** it exits with a nonzero status and a message naming the unsupported combination

### Requirement: Steering is logged per request
The server's per-request log line SHALL state whether the request was steered.

#### Scenario: Log line
- **WHEN** a steered and an unsteered request are answered
- **THEN** the steered request's progress lines carry a `steer` flag and the unsteered request's lines do not; the request trace records `steering: on` or `off`

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
