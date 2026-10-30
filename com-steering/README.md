# com-steering

The steering configuration this child ships (the `sf-ds4-1flash-candor`
profile), the record of how its directions were derived, and the tool that
packages and inspects a profile. The source direction vectors are not shipped:
the profile is self-contained (it embeds its matrices), and the investigation
behind it is closed, so only the provenance is kept here, not the raw `.f32`
files. The runtime mechanism — the fold site, the options, the rank-2 second
slot — is documented in [`dir-steering/README.md`](../dir-steering/README.md);
this folder is the material, not the machinery.

Steering is refused by default on V4.1 and stays opt-in. A profile is the only
way in, so loading one is a deliberate act.

## Using a profile

```sh
./sf-ds4-1flash --ssd-streaming --steering-profile sf-ds4-1flash-candor -p "..."
./sf-ds4-1flash-server --ssd-streaming --steering-profile-on-request sf-ds4-1flash-candor
```

The CLI and eval apply the profile to every prompt. The server loads it off,
and a request turns it on with a `-steering` model id such as
`deepseek-v4.1-flash-steering` (`docs/SERVER.md`, Steering per request).

A bare name resolves to `com-steering/profiles/<name>.sfsteer`; a name that
matches nothing makes the engine list the profiles that exist. A path works too.
The CLI's `--dir-steering-*` options are refused together with a profile.

What a steered session gives up: session payloads and snapshots are refused
in the CLI and eval, the server keeps steered disk entries in their own store,
`<kv-disk-dir>/steering`, emptied whenever the profile's bytes change, and a
steered session whose profile gates a slot to one reasoning phase, or
schedules its scale, decodes on its own rather than sharing a batch.

## Profiles

### `sf-ds4-1flash-candor`

**The child's recommended default steering profile** (change `406`). Steering is
still refused by default and the profile is still the opt-in; "default" means this
is the configuration to pass, not an auto-applied edit. Its slots, hashes,
scales, phases and accepting-run ids are recorded in this file (the table below
and `result.md`): **41.3 /44** non-think (`C41 D1 R2`), **41.0** think (`C41 D0 R3`, reasoning loop 3/44 against 13/44 before the closure channel), over the
`msuiche-1017@7` baseline's 26.7 (`com-steering/result.md`, `kpi.md`). `mrfk-q0@7`
alone is the rank-1 reference (ties 41.6 non-think, 37.0 think). Benign /
over-refusal of these directions is an open measurement, not a claimed result.

| | |
|---|---|
| Model | DeepSeek V4.1 Flash, `1017` checkpoint, IQ2_XXS-Q2_K-imatrix |
| Site | `v41_attn_input_weighted_fold_post_engram`, revision 2 |
| Slot 1 | `v41-q0dwarf-equi` at scale 7, **both** phases |
| Slot 2 | `v41-mrfk-q1` at scale 7, **think** phase only |
| Closure | `v41-closure-satisfied`, additive, **think** only: 0.4 from onset 2700..3100 (by think-level) over 256 tokens, 0.9 from onset+2000 over 512 (change `419`, promoted in `420`); the non-think output is byte-identical to the profile without it. `close0.25`, `close0.5` and `close2` stay as named alternatives |
| Size | 2 458 614 bytes (header + three 40x5120 f32 matrices) |

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

# build (the source .f32 directions are not shipped; pass any direction file)
com-steering/make_profile.py com-steering/profiles/<name>.sfsteer \
    --name <name> --description "..." \
    --slot <path>/<first>.f32  <scale> both \
    --slot <path>/<second>.f32 <scale> think
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
...  closure matrix                   40 * 5120 float32   (only with a "closure" object, 419)
```

The engine reads `site`, `layers`, `width`, and each slot's `scale` and `phase`
(`both`, `think` or `answer`), plus the optional schedule keys of 418
(`decay_tokens`, `decay_final`, `decay_hold`, `decay_final_answer`; the
explored `decay_phase`, `ramp_tokens` and `ramp_low` slot keys were not adopted
and a profile that names them is refused) and the optional top-level
`closure` object of 419: an additive third direction `h += a(t)·c[layer]` at the
same site, thinking phase only, with `scale` (small by design), `onset_min`
(think tokens before any push at reasoning effort ≤ 10), `onset_max` (the same
at effort 100, linear between; the CLI's `--think-level` sets the level, unknown
counts as 75) and `ramp_tokens` (smoothstep rise); an optional second stage
(`scale2`, `after_tokens`, `ramp2_tokens`) raises `a(t)` again from `scale` to
`scale2` starting `after_tokens` past the onset, so the door is offered gently
first and firmly later. The closure direction was built as the contrastive
mean of the site rows (the 40 layer rows read by attention, captured per decode
token) between prompts that closed cleanly and prompts that looped. The two 419
probes that measured the `</think>` logit gap and captured those rows were
removed once the closure tuning closed; the shipped profile embeds the result.
Everything else — the profile name, the
description, each slot's source filename and the SHA-256 of its matrix bytes —
is provenance the engine carries without interpreting. The requirements are in
[`openspec/specs/directional-steering/spec.md`](../openspec/specs/directional-steering/spec.md).

## Directions (provenance)

The raw `.f32` directions and their `.json` sidecars are **not shipped** — the
`candor` profile embeds the three it uses, and the investigation that chose them
is closed. This is the record of what those directions were and how they were
derived, all measured on the `1017` checkpoint; `v41-closure-satisfied` cannot be
rebuilt from this tree since the 419 site-capture probe was removed, and the
profile embeds it.

The profile embeds three directions:

| Direction in the profile | Role | How it was derived |
|---|---|---|
| `v41-q0dwarf-equi` | slot 1, scale 7, both phases | per-layer bisector (equiangular, unit) of `mrfk-q0` and `dwarfstar-wo` |
| `v41-mrfk-q1` | slot 2, scale 7, think only | `mrfakename` q1 refusal axis |
| `v41-closure-satisfied` | additive closure channel (419) | contrastive mean of the site rows captured by the (removed) 419 probe between prompts that closed the reasoning loop cleanly and prompts that looped; raw displacement rows, not unit |

Their parents and the alternatives that were weighed and dropped:

- `v41-mrfk-q0` / `v41-mrfk-q1` — the two columns of `Q` (5120x2, orthonormal) in
  `abliteration-edit.npz` of the Hugging Face model
  `mrfakename/DeepSeek-V4.1-Flash-1017-abliterated`: a global rank-2 refusal
  subspace measured over chat and think. Each is a global direction (the same
  unit row on layers 1-39, row 0 zero); `q0` is the dominant axis and, alone,
  the rank-1 reference. The extraction script was a scratch file, never in this
  tree.
- `v41-dwarfstar-wo` — the per-layer difference of `attn_output_b` (the tensor
  that writes into the fold site) between our `1017` IQ2_XXS-Q2_K-imatrix base
  and `AtomicChat`'s DwarfStar GGUF of the same quant, whose refusal edit is baked
  into 122 residual-write tensors (`attn_output_b`, `ffn_down_shexp`,
  `ffn_down_exps` x40 each, `engram_kv` x2; scale 2.0, rank-1). All 40 layers
  came out edited and mutually parallel (|cos| 1.0), a global direction like
  `q0`, with `cos(dwarfstar-wo, q0)` 0.71: two independent abliterations of the
  `1017` agree. Alone it peaked at scale 8 (39.9 /44 non-think, against `q0@7`
  41.6), failing on prompts disjoint from `q0`'s, which is why the two were
  bisected. Its derivation script was never in this tree.
- `v41-q0dwarf-interleave` — same two parents as `equi` but alternating by layer
  (`q0` on even layers, `dwarfstar-wo` on odd); 10.0 on the 12-id screen against
  the bisector's 11.0, below both parents.
- `v41-msuiche-1017` — msuiche's control vector converted to `.f32`; the baseline
  the shipped pair beat (26.7 vs 41.x).

The accepting runs and standing numbers are in `result.md`, the scoring rule in
`kpi.md`, and the roads measured and dropped on the way in `investigation.md`,
"Closed roads".
