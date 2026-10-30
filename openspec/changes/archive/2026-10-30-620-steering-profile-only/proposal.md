# Proposal

## Why

Steering on V4.1 is now configured through one `.sfsteer` profile: `sf-ds4-1flash-candor`, `com-steering/`. The profile carries what the raw options could express (the slot vectors and scales) and more that they could not: per-phase gates without environment variables, the decay schedule (`418`) and the closure channel (`419`). The raw options are the surface of the experiments that came before profiles:
- the opt-in layer `--allow-v41-steering` / `DS4_ALLOW_V41_STEERING` (`400`);
- the residual-site scales `--dir-steering-residual`, `--dir-steering-file-2` and `--dir-steering-residual-2` (`401`, `412`);
- the environment gates `DS4_STEERING_THINK_PHASE` and `DS4_STEERING_THINK_PHASE2`.

No script, test or Makefile target in the repository passes them any more. Only documentation and the `directional-steering` spec still describe them.

Changes `630`-`650` make steering selectable per session and per server request, and give steered requests their own KV cache. Every admission path is one more case each of those changes would have to switch, isolate and identify. The owner has decided that in this child steering exists only through a profile. This supersedes, for this child, the StarForge rule that kept the raw steering tooling in every child (rule 4).

## What Changes

- **BREAKING, removed from the CLI, `sf-ds4-1flash-eval` and the server:**
  - `--dir-steering-residual`;
  - `--dir-steering-file-2`;
  - `--dir-steering-residual-2`;
  - `--allow-v41-steering`.
- **BREAKING, server: `--dir-steering-file`, `--dir-steering-ffn` and `--dir-steering-attn` are removed.** Only their parse branches and the server's implicit `ffn = 1` default go, so an old command line fails as an unknown option.
- **BREAKING, eval: `--dir-steering-file` is removed.** Upstream's eval has no steering options; this one was added here together with the residual scale and the opt-in.
- **The CLI keeps upstream's three options** (`--dir-steering-file`, `-ffn`, `-attn`) to keep sync conflicts small. On V4.1 they reach upstream's refusal, as before the opt-in existed. The CLI's live `/steer` (upstream) stays as it is.
- **BREAKING, environment:**
  - `DS4_ALLOW_V41_STEERING`, `DS4_STEERING_THINK_PHASE` and `DS4_STEERING_THINK_PHASE2` are no longer read.
  - Their lines leave `ds4_env.def`. `make env-check` enforces both directions, so a leftover read fails.
- **The opt-in layer goes.**
  - The V4.1 support check in `ds4_engine_open` (`ds4.c:30633`) returns to upstream's expression, plus one `sf:` term: "a profile is loaded".
  - A raw `--dir-steering-file` on V4.1 therefore fails with upstream's message, word for word, and a profile is the only way in.
- **The engine API shrinks to what a profile needs.**
  - `ds4_engine_options` loses the four `sf` fields: `directional_steering_residual`, `allow_v41_steering`, `directional_steering_file2` and `directional_steering_residual2`.
  - The checks that existed only for them go: "residual needs a file" and "residual-2 needs file-2".
  - The profile-versus-options conflict check keeps only the upstream options (file, FFN, attention).
  - The engine's internal slot fields stay. The profile loader fills them, and the validation, the rank-2 orthogonality report, the gates, decay and closure are untouched.
- **The server's `--kv-disk-dir` guard** (`ds4_server.c:14961`) keeps its meaning. Its condition reduces to "a profile is loaded". `640` turns it into per-request behaviour and `650` removes it.
- **`--steering-profile` keeps today's meaning in every binary** in this change. The server's flag is renamed in `640`.
- **Docs follow the code.** Paragraphs describing the removed options are deleted, not adapted:
  - `ds4_help.c`;
  - `AGENTS.md` (Identity "Steering" row);
  - `README.md`;
  - `dir-steering/README.md` and `dir-steering/vectors/README.md`;
  - `com-steering/make.md` and `com-steering/spec.md`.

  `docs/upstream-prs.md` lines `400`, `401` and "rank-2, gates, profiles" are rewritten to state that the opt-in and raw options are gone and that the V4.1 site is reached through a profile.

Non-goals:
- No change to what a loaded profile computes.
- No change to the `.sfsteer` format or to `com-steering/make_profile.py`.
- No change to the upstream V4 FFN/attention graph code or to `dir-steering/` tooling beyond its docs.
- The StarForge orchestrator's `AGENTS.md`/`SPEC.md` (rule 4, SPEC §B) are out of scope and not updated. This child's `AGENTS.md` records the deviation.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `directional-steering`:
  - removes "V4.1 steering opt-in", "Presence-based environment opt-in" and "Admission-only no-op";
  - restates "V4.1 weighted-fold intervention" and "Second residual direction" as profile slots instead of options;
  - restates "Unsupported active-site diagnostics": no opt-in precedence; the server has no FFN/attention options;
  - restates "Per-slot reasoning-phase gate": gates come only from the profile;
  - restates "Profile admission and validation": the profile is the only admission; the conflict check covers file, FFN and attention.
- `steering-vectors`: "Default provenance and opt-in preserved" no longer refers to an opt-in refusal. Steering stays off unless a profile is passed.

## Impact

- **Code:** `ds4.c` (engine open admission and checks), `ds4.h` (`ds4_engine_options`), `ds4_cli.c`, `ds4_eval.c`, `ds4_server.c` (argument parsing, kv guard condition), `ds4_help.c`, `ds4_env.def`.
- **Sync:** the support-check expression moves closer to upstream (fewer conflicts). The server's removed upstream option branches add one small conflict site, recorded with an `sf-ablate(steering)` marker.
- **Verification:**
  - `make test`, which includes `env-check`.
  - The CLI with `--steering-profile sf-ds4-1flash-candor` produces byte-identical text before and after the change, thinking on and off. This is the same evidence `416` used.
  - Unsteered runs are unchanged, and the parity oracle (no steering) passes.
- **Order:** second. It shrinks the surface that `630` (per-session switch), `640` (request selection) and `650` (cache identity) have to cover, to one source: the profile.
