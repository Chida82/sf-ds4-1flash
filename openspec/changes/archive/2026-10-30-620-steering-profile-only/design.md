# Design

## Context

How steering is admitted today, in `ds4_engine_open` (`ds4.c:30528-30580`, `30625-30650`):

1. "A scale needs a file" checks for attention, FFN and residual, plus "residual-2 needs file-2".
2. The raw options fill the engine's slot fields (`directional_steering_file`, `_residual_scale`, `_file2`, `_residual2_scale`).
3. `DS4_STEERING_THINK_PHASE`/`2` fill the slot gates.
4. A profile, which refuses raw options alongside it, overwrites the slot fields through `ds41_steering_profile_open`.
5. The V4.1 support check ORs four admissions into upstream's file term: `opt->allow_v41_steering`, `DS4_ALLOW_V41_STEERING`, "a profile is loaded", and upstream's own `(!file || !file[0])` together with the `file2` equivalent.

Upstream's expression has only `(!opt->directional_steering_file || !opt->directional_steering_file[0])`.

Frontends:
- **CLI** (`ds4_cli.c:1934-1959`, `2021`): upstream's `--dir-steering-file`/`-ffn`/`-attn`, with the implicit `ffn = 1` default, plus the four sf options and `--steering-profile`.
- **Server** (`ds4_server.c:14751-14798`): the same set.
- **Eval** (`ds4_eval.c:1210-1215`, `1699-1707`, `4764-4767`): `--dir-steering-file`, `--dir-steering-residual`, `--allow-v41-steering` and `--steering-profile`. Upstream's eval has no steering options.

## Goals / Non-Goals

**Goals:**
- One admission (the profile).
- The support check back to upstream's text, plus one term.
- No change to what a profile computes.
- The fewest edits to upstream lines.

**Non-Goals:**
- Touching the engine's internal slot fields, the profile parser, the loaders, gates, decay, closure or the V4 graph's FFN/attention code.
- Renaming the server flag (`640`).
- Removing the CLI's upstream options or `/steer`.

## Decisions

### D1. The support check

The expression becomes upstream's line, unchanged, ORed with one `sf:` term:

```
((opt->steering_profile && opt->steering_profile[0]) ||   /* sf: a profile is the only steering admission */
 (!opt->directional_steering_file || !opt->directional_steering_file[0])) &&
```

A raw file without a profile therefore fails with upstream's message, word for word. A profile together with a raw file never reaches this line: step 4's conflict check refuses it first. The `sf:` comment above the old OR, which cites SPEC rule #4, goes with it.

### D2. Engine options

`ds4_engine_options` loses `directional_steering_residual`, `allow_v41_steering`, `directional_steering_file2` and `directional_steering_residual2`. These are sf fields, so there is no upstream conflict. In `ds4_engine_open`:
- the "needs a file" check keeps only attention and FFN, which is upstream's form;
- the "residual-2 needs file-2" check goes;
- the raw fill of `_residual_scale`, `_file2` and `_residual2_scale` goes;
- the environment gate block goes, and the slot gates default to both phases until a profile sets them;
- the profile conflict check reads `e->directional_steering_file || opt->directional_steering_attn != 0.0f || opt->directional_steering_ffn != 0.0f`.

The internal engine fields stay, because `ds41_steering_profile_open` writes them. `cpu_load_directional_steering`'s branch for the second file stays: it loads a profile's second slot from `e->directional_steering_file2`, which the profile sets. That gets verified in a task, not assumed.

### D3. Frontends

- **CLI:** delete the four sf branches. Upstream's three branches and the `ffn = 1` default stay; the `directional_steering_scale_set` flag is still needed by `-ffn`/`-attn`.
- **Server:** delete the three upstream branches, the four sf branches and the `ffn = 1` default, and with them `directional_steering_scale_set`. The deletion of upstream lines gets one `sf-ablate(steering):` marker where the branches were.
- **Eval:** delete `--dir-steering-file`, `--dir-steering-residual` and `--allow-v41-steering` and their config fields. `--steering-profile` stays.
- **Server kv guard:** the condition (`ds4_server.c:14961`) becomes `cfg.engine.steering_profile && cfg.engine.steering_profile[0]`. The log text is unchanged.

### D4. Environment registry

`ds4_env.def` loses `DS4_ALLOW_V41_STEERING`, `DS4_STEERING_THINK_PHASE` and `DS4_STEERING_THINK_PHASE2`. `make env-check` fails if any read remains, and also fails if a line stays with no reader. Any other line whose description names a removed option is reworded to name the profile.

### D5. Docs

Paragraphs describing removed options are deleted, not adapted (AGENTS.md rule 4 of this child, "docs follow code"). The candidates are found with:

```
git grep -n -e "--dir-steering-residual" -e "dir-steering-file-2" -e "allow-v41-steering" \
  -e DS4_ALLOW_V41_STEERING -e STEERING_THINK_PHASE -- ':!openspec/changes/archive'
```

Files: `README.md` (512-523), `AGENTS.md` (Identity "Steering" row), `dir-steering/README.md`, `dir-steering/vectors/README.md`, `com-steering/make.md`, `com-steering/spec.md`, `ds4_help.c` (213-220), `docs/upstream-prs.md` (40-42).

Archived changes are history and stay as written. `openspec/specs/` is updated by archiving this change.

`AGENTS.md` records the deviation from the StarForge steering rule. In this child, steering exists only through a profile.

### D6. Evidence that a profile computes the same

There is no model-less test for the profile path (`416` removed them). The evidence is the one `416` used: the CLI with `--steering-profile sf-ds4-1flash-candor`, on main and on the branch, on the same prompt, thinking on and off, greedy, produces byte-identical text. Both runs use `--ssd-streaming` and the largest admitted cache.

## Risks / Trade-offs

- [A personal script outside the repo still passes a removed option] → It fails at startup with "unknown option", which is loud. The proposal marks each removal BREAKING.
- [A profile's second slot silently stops loading because the second-file branch was cut too far] → D6 compares a two-slot profile (candor has two slots plus closure), and the engine prints the rank-2 orthogonality line at open; the task checks for that line.
- [Upstream edits the server's three steering branches] → One conflict site, resolved by keeping them deleted; rerere replays it.
- [Removing a documented experimental path makes new vector screening slower] → A vector is screened by building a one-slot profile with `make_profile.py`, one command. `com-steering/make.md` gets that example.

## Migration Plan

Operators who used raw options build a profile:

```
python3 com-steering/make_profile.py ... -o com-steering/profiles/<name>.sfsteer
./sf-ds4-1flash --steering-profile <name> ...
```

`com-steering/make.md` holds the exact command. There is no rollback path other than reverting the change.
