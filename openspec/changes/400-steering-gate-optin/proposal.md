# Proposal

## Why

V4.1 rejects a steering file at engine open. Research needs an explicit way to lift only that restriction, without changing the default refusal or claiming that accepting a file makes an intervention effective.

## What Changes

- Keep `--allow-v41-steering` on the CLI and server and the `DS4_ALLOW_V41_STEERING` environment opt-in. The bench has no steering block and is outside this change.
- Preserve the existing presence-based environment semantics: unset does not opt in; a present variable does, including an empty value or `0`. Document `=1` as the recommended spelling, not as a value parser.
- Lift only the steering-file term in V4.1's support check. Keep the other restrictions and the default upstream error byte-for-byte.
- Prove that an opt-in without an active intervention preserves logits, KV and Engram, not merely completion text.
- Correct the bring-up documentation: the legacy FFN/attention hooks are not connected to the active V4.1 graph. This change is an admission gate; `401` owns the usable hook and unsupported-site diagnostics.

## Capabilities

### New Capabilities
- `directional-steering`: explicit V4.1 steering admission, with unchanged default refusal and no-op behavior. This is the root of the capability extended by the other in-flight steering changes.

### Modified Capabilities
None. No durable directional-steering main spec exists yet.

## Impact

- `ds4.c`, `ds4.h`: admission predicate and engine option.
- `ds4_cli.c`, `ds4_server.c`, `ds4_help.c`: opt-in surface; no bench-only flag.
- `ds4_env.def`: environment classification.
- Existing model-less/frontend tests and `tests/test_deepseek41_graph.c`: executable gate and no-op checks.
- `README.md`, `dir-steering/README.md`, `docs/upstream-prs.md`: truthful admission-only scope and child divergence, updated with implementation.
- No hook, vector, cache-format, schedule or inference-kernel changes belong here.
