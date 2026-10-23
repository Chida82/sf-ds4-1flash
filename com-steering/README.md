# com-steering

Steering configurations this child ships, the direction vectors they are built
from, and the tool that packages them. The runtime mechanism — the fold site,
the options, the rank-2 second slot — is documented in
[`dir-steering/README.md`](../dir-steering/README.md); this folder is the
material, not the machinery.

Steering is refused by default on V4.1 and stays opt-in. A profile is itself the
opt-in, so loading one is a deliberate act.

## Using a profile

```sh
./sf-ds4-1flash --ssd-streaming --steering-profile sf-ds4-1flash-candor -p "..."
./sf-ds4-1flash-server --ssd-streaming --steering-profile sf-ds4-1flash-candor
```

A bare name resolves to `com-steering/profiles/<name>.sfsteer`; a name that
matches nothing makes the engine list the profiles that exist. A path works too.
`--steering-profile` replaces the `--dir-steering-*` options and is refused if
combined with them.

What a steered run gives up, unchanged from a steered run configured by hand:
session payloads and snapshots are refused, the server does not open
`--kv-disk-dir`, and a session whose profile gates a slot to one reasoning phase
decodes on its own rather than sharing a batch.

## Profiles

### `sf-ds4-1flash-candor`

| | |
|---|---|
| Model | DeepSeek V4.1 Flash, `1017` checkpoint, IQ2_XXS-Q2_K-imatrix |
| Site | `v41_attn_input_weighted_fold_post_engram`, revision 2 |
| Slot 1 | `v41-q0dwarf-equi` at scale 7, **both** phases |
| Slot 2 | `v41-mrfk-q1` at scale 7, **think** phase only |
| Size | 1 639 041 bytes (header + two 40x5120 f32 matrices) |

The two directions are nearly orthogonal (median `|cos|` 0.105 over the 39
non-zero layers), which the engine prints at open: the pair composes as a clean
two-dimensional removal rather than folding one axis twice.

Slot 2 is confined to the reasoning phase because that is the only place it
helps; applied to the answer as well it made results worse. Slot 1 runs in both.

**This profile has no automated test.** The model-less checks that covered the
fold's routes, the rank-2 off path and the profile parser were removed (see the
archived change `416`). The evidence behind the current file is a one-off
model-backed comparison recorded on 2026-10-23: the profile, the equivalent run
configured with raw options, and the same raw-option run on the pre-prune binary
all produced byte-identical text, in both reasoning and non-reasoning mode.

## Building and inspecting a profile

```sh
# inspect: prints the header, verifies each matrix against its recorded hash
com-steering/make_profile.py --show com-steering/profiles/sf-ds4-1flash-candor.sfsteer

# build
com-steering/make_profile.py com-steering/profiles/<name>.sfsteer \
    --name <name> --description "..." \
    --slot com-steering/vectors/<first>.f32  <scale> both \
    --slot com-steering/vectors/<second>.f32 <scale> think
```

The tool applies the engine's own validation before writing: 40x5120 float32,
finite, row 0 all zero, every other row unit within 1e-2 or all zero. A slot
scale of 0 is refused — drop the slot instead.

### File format (`.sfsteer`)

```
 0   "SFSTEER1"                       8 bytes, magic
 8   header length                    uint32, little-endian
12   JSON header                      <header length> bytes
...  slot 1 matrix                    40 * 5120 float32
...  slot 2 matrix                    40 * 5120 float32   (only if two slots)
```

The engine reads `site`, `layers`, `width`, and each slot's `scale` and `phase`
(`both`, `think` or `answer`). Everything else — the profile name, the
description, each slot's source filename and the SHA-256 of its matrix bytes —
is provenance the engine carries without interpreting. The requirements are in
[`openspec/specs/directional-steering/spec.md`](../openspec/specs/directional-steering/spec.md).

## Vectors

All measured on the `1017` checkpoint. A raw `.f32` carries no provenance of its
own, so each one should have a `.json` sidecar beside it.

| File | Provenance |
|---|---|
| `v41-q0dwarf-equi.f32` | sidecar present — built from the two below |
| `v41-q0dwarf-interleave.f32` | sidecar present — same two inputs, alternating by layer |
| `v41-msuiche-1017.f32` | sidecar present — converted control vector |
| `v41-mrfk-q0.f32` | **missing** |
| `v41-mrfk-q1.f32` | **missing** |
| `v41-dwarfstar-wo.f32` | **missing** |

The three gaps matter: `v41-mrfk-q0` is slot 1's parent and `v41-mrfk-q1` is
slot 2 itself, so the shipped profile currently rests on two files whose origin
is recorded nowhere except `vectors/mrfk_extract.py`, the script that wrote
them. Closing this is a prerequisite for the change that pins a shipped default
to the run that chose it.
