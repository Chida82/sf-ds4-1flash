# Tasks

## 1. Opt-in

- [ ] 1.1 Add `--allow-v41-steering` to `ds4_cli.c`, `ds4_server.c`, `ds4_bench.c`,
  and an `ds4_engine_options` bool; `DS4_ALLOW_V41_STEERING` read at the same point.
  Verify `--help` lists it and the unknown-flag path is unaffected.
- [ ] 1.2 In `ds4.c:30133`, gate the `directional_steering_file` term on the opt-in;
  leave the refusal string and every other term byte-identical. Mark `sf:`. Verify a
  diff against upstream at the site shows only the added condition.
- [ ] 1.3 Classify `DS4_ALLOW_V41_STEERING` in `ds4_env.def` (`enable`, unset).
  Verify `make env-check` passes and engine open prints it when set.

## 2. Gate behavior

- [ ] 2.1 Without the opt-in, `--dir-steering-file X` prints the exact upstream line
  and exits 1. Verify the line is byte-identical to `tests/parity_prompts.txt:5`.
- [ ] 2.2 With the opt-in and no file (or zero scales), no direction tensor is
  allocated. Verify
  `make test-deepseek41-decode-switch SWITCH=DS4_ALLOW_V41_STEERING` (65-token
  logit/KV/Engram bitwise); add the switch to that harness if it is not already a
  no-op case.

## 3. Docs

- [ ] 3.1 `dir-steering/README.md` and `README.md`: V4.1 starts with steering under
  `--allow-v41-steering`; the refusal still shown without it. Verify no doc claims
  steering is supported by default. Keep the quoted refusal block verbatim.
- [ ] 3.2 `docs/upstream-prs.md`: record the divergence (no upstream PR); provenance
  in the registry/commit, not in source.

## 4. Integration

- [ ] 4.1 `make test` (incl. env-check),
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash` on the
  default path (no opt-in) token-identical,
  `openspec validate 400-steering-gate-optin --strict`. No commit or push without a
  request.
