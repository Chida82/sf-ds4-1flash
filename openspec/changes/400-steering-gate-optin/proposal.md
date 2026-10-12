# Proposal

## Why

V4.1 refuses to start with `--dir-steering-file`: the support gate (`ds4.c:30133`)
lists `directional_steering_file` among the unsupported options and prints the
upstream refusal. That text is upstream's and stays word for word (SPEC §4), even
though this child keeps the steering tooling and the GPU graph already carries the
steering hooks. The owner wants steering usable on V4.1 for refusal-removal research
and its validation (`400`-`405`). An explicit opt-in must lift the refusal without
touching its wording for the default path.

## What Changes

- **Opt-in flag.** `--allow-v41-steering` (CLI, server, bench) and
  `DS4_ALLOW_V41_STEERING=1`. When set, the `supported` predicate drops only its
  `directional_steering_file` term; every other term (distributed, load_slice,
  tests, power, context) is unchanged.
- **Refusal text untouched.** Without the opt-in, a passed `--dir-steering-file`
  prints the exact upstream line and exits, as today. The string is not edited.
- **Disabled path bitwise.** Without the opt-in, or with it but no file / zero
  scales, the engine allocates no direction tensor and output stays bitwise
  identical (no-op gate).
- **Env classified.** `DS4_ALLOW_V41_STEERING` added to `ds4_env.def` (`enable`,
  normal state unset), so `make env-check` passes and engine open reports it when
  set.
- This change only lifts the gate. It does **not** make the applied edit correct:
  the existing `ffn_out` hook is the wrong site for the V4.1 vectors (`401`). A file
  loaded after this change alone is applied at that wrong site; `401` adds the
  correct one.

## Capabilities

### New Capabilities
- `directional-steering`: runtime directional steering on V4.1, off by default,
  behind an explicit opt-in, with the upstream refusal preserved for the default
  path.

### Modified Capabilities
None.

## Impact

- `ds4.c`: the `supported` predicate at `30133` reads the opt-in; the refusal string
  is unchanged. Marked `sf:` as a deliberate divergence (a permanent sync-conflict
  site; rerere replays it).
- `ds4_cli.c`, `ds4_server.c`, `ds4_bench.c`, `ds4_help.c`: the flag.
- `ds4_env.def`: the env.
- `dir-steering/README.md`, `README.md`: V4.1 now starts with steering under the
  opt-in; the refusal still shown without it.
- `docs/upstream-prs.md`: child divergence, no upstream PR; provenance in the
  registry/commit, not in source.
