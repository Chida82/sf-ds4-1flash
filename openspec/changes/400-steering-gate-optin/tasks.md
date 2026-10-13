# Tasks

Status 2026-10-13: the gate is implemented and verified at the frontend/engine level
(build clean; env-check 502->503; default path refuses byte-for-byte with exit 1;
`--allow-v41-steering` lifts it and generates; `make test` EXIT=0; `openspec validate
--strict` passes). Verified against the tree, not from memory: README.md:515 and
dir-steering/README.md:23 carry the opt-in, ds4_env.def:9 classifies the env. Still
open, each short: the decode-switch bitwise harness (2.2), the parity oracle (4.1), the
`docs/upstream-prs.md` divergence note (3.2), and a scope decision on bench (1.1).

## 1. Opt-in

- [~] 1.1 `--allow-v41-steering` is in `ds4_cli.c`, `ds4_server.c` and `ds4_help.c` with
  the `ds4_engine_options` bool, and `DS4_ALLOW_V41_STEERING` is read at the same
  point; `--help` lists it. NOT in `ds4_bench.c`: the bench carries no steering flags
  at all (`--dir-steering-file` included, see `401`), so an opt-in there would gate
  nothing. DECIDE: either narrow this task to cli+server by design, or give the bench
  the whole steering block. Do not add the bare flag.
- [x] 1.2 In `ds4.c` the `directional_steering_file` term is gated on the opt-in; the
  refusal string and every other term are byte-identical, marked `sf:`.
- [x] 1.3 `DS4_ALLOW_V41_STEERING` classified in `ds4_env.def` (`enable`, unset);
  `make env-check` passes (503) and engine open prints it when set.

## 2. Gate behavior

- [x] 2.1 Without the opt-in, `--dir-steering-file X` prints the exact upstream line and
  exits 1 (verified byte-for-byte).
- [ ] 2.2 With the opt-in and no file (or zero scales), no direction tensor is
  allocated. NOT RUN: `make test-deepseek41-decode-switch SWITCH=DS4_ALLOW_V41_STEERING`
  (65-token logit/KV/Engram bitwise), ~30 s with the model; add the switch to that
  harness if it is not already a no-op case.

## 3. Docs

- [x] 3.1 `dir-steering/README.md` and `README.md`: V4.1 starts with steering under
  `--allow-v41-steering`; the refusal still shown without it, quoted verbatim.
- [ ] 3.2 `docs/upstream-prs.md`: record the divergence (no upstream PR); provenance in
  the registry/commit, not in source. NOT DONE: no 400 entry exists in that file.

## 4. Integration

- [~] 4.1 `make test` (incl. env-check) EXIT=0 and `openspec validate
  400-steering-gate-optin --strict` DONE. NOT RUN: `SF_PARITY_FLAGS=--ssd-streaming
  tools/parity-check.sh sf-ds4-1flash` on the default path (no opt-in) token-identical.
  Commit authority on `sf/steering` is standing for this steering work; no push.
