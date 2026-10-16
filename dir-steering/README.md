# Directional Steering

Directional steering is a runtime activation edit for DS4. A steering file is a
flat `f32` matrix with one normalized hidden-width direction per normal
transformer layer. During inference, ds4 can apply the edit after attention
outputs or FFN outputs (the V4 hooks), or, on V4.1, to the attention-input fold:

```text
y = y - scale * direction[layer] * dot(direction[layer], y)
```

Positive scale removes the represented direction. Negative scale amplifies it.
With no steering file or zero scales, ds4 follows the normal inference path.

**DeepSeek V4.1 Flash refuses steering by default.** The engine refuses to start
when `--dir-steering-file` is passed, exactly as it does upstream:

```text
ds4: V4.1 requires Metal or single-GPU CUDA per rank (optional network tensor parallelism); DSpark, steering and legacy diagnostics are not supported (maximum context 1048576)
```

`--allow-v41-steering` on the CLI or the server lifts only this refusal, on
single-box Metal. `DS4_ALLOW_V41_STEERING` does the same whenever it is set, to
any value: empty and `0` opt in too, `=1` is only the usual spelling. Every other
unsupported condition still refuses, and without the opt-in the message above is
byte-for-byte unchanged. The bench has no steering options.

The opt-in is admission only: it lets the engine load a file and applies nothing.
On V4.1 the one live site is the residual one, `--dir-steering-residual` (change
`401`, [contract](../openspec/changes/401-residual-steering-hook-msuiche/specs/directional-steering/spec.md),
described below). `--dir-steering-ffn` and `--dir-steering-attn` are hooks of
the older V4 graph, which V4.1 never allocates: a nonzero value is refused at
startup rather than accepted without effect, and since a file alone implies
`--dir-steering-ffn 1` in the CLI and server, name the residual scale explicitly.

The tooling, the file format and the runtime options below are kept unchanged
(SPEC.md §B: steering stays in every child even where the model rejects it), so
a future model or an upstream change can use them without reinventing them.
The checked-in vector under `out/` was built for another model -- its shape is
`43 x 4096`, while this model is 40 layers of 5120 -- and is kept only as a
format example.

## Runtime Options

```text
--dir-steering-file FILE   load one f32 direction per normal model layer (40x5120 on V4.1)
--dir-steering-ffn F       apply steering after FFN outputs; default is 1 when a file is provided (V4 hook; V4.1 refuses a nonzero value)
--dir-steering-attn F      apply steering after attention outputs; default is 0 (V4 hook; V4.1 refuses a nonzero value)
--dir-steering-residual F  steer the V4.1 attention-input fold; default is 0
--dir-steering-file-2 FILE  rank-2: a second direction file (should be orthogonal to the first, e.g. fuse_directions.py 'ortho')
--dir-steering-residual-2 F rank-2: constant scale for the second direction at the same site; default 0 (off, no 403 schedule)
--dir-steering-residual-decay-tokens N        (403, experimental) decay the residual scale from its start to its final over N generated tokens; 0 = constant
--dir-steering-residual-decay-final F         (403, experimental) the residual (minimum) scale the decay holds at; default 0
--dir-steering-think-residual-decay-tokens N  (403, experimental) decay window for the thinking phase; 0 = use the answer window
```

Three application sites, each with its own scale:

| Site | Flag | Model |
|---|---|---|
| FFN output (pre-residual) | `--dir-steering-ffn` | V4 graph only |
| Attention output | `--dir-steering-attn` | V4 graph only |
| Attention-input fold | `--dir-steering-residual` | V4.1 (`401`) |

Setting `--dir-steering-residual` does not enable the FFN site, and a control
vector is only meaningful at a site whose tensor it was derived for, which is
the caveat of the next section.

### The V4.1 site (`401`)

`--dir-steering-residual F` edits the **weighted HC attention-input fold** of
layers 1-39: the four residual streams folded into one 5120-wide row by the
previous sublayer's mixer weights, after Engram on layers 1 and 14, before the
attention norm. The runtime names it `v41_attn_input_weighted_fold_post_engram`,
intervention revision 2, and prints both at startup. Row N of the file is
applied before the attention of layer N (a direct index; row 0 is zero). The
edit is `h -= F*d*dot(d,h)` on the fold rounded to BF16, in f32, with no second
rounding before the norm, on every route that produces an attention input:
decode, batch prefill and the rows the wide-sweep decoder suffix reconstructs
(`make test-deepseek41-steering-routes`). With a unit `d`, F=1 removes the
component along `d`, 2 reflects it, 4 and 8 multiply it by -3 and -7.

**Rank-2 (`--dir-steering-file-2 FILE2 --dir-steering-residual-2 G`).** A second
direction is removed at the same site with its own constant scale, as a second
in-place fold right after the first: `h -= G*d2*dot(d2,h)`. When `d2` is
orthogonal to `d` per layer — e.g. `fuse_directions.py`'s `ortho` output,
`d2 = unit(b - (d.b)d)` — the two sequential removals equal projecting out their
2D span exactly, so the first direction's effect is untouched. Non-orthogonal
pairs still run, but compose as two rank-1 removals rather than a clean 2D
projection. The second slot has no `403` decay schedule (constant scale only),
shares the opt-in and the disable env, and the persistence/KV guards apply when
either scale is nonzero. Motivation: one vector (rank-1) can only rotate the
removed direction; a second orthogonal direction adds a dimension, which is what
reaches refusals the single direction leaves (measured union ceiling, see
`docs/steering-measurements.md`).

This fold is transient, and it is **not** the post-layer residual
(`residual_stream_post_layer`) the msuiche vector was derived at: the direct
layer mapping is a baseline experiment, not a replication of the published
result (`405` compares sites, `402` measures behaviour). The scale defaults to
0. A first-token screen on 2026-10-13 (25 prompts) put the msuiche vector's
useful range at this site around 4-8, with 0.5, its published alpha, a near
no-op here; those are screening candidates, not a validated default.

The file is validated at engine open, before any session exists: 40x5120 f32,
finite, row 0 zero, every other row unit within 1e-2 or all zero (a masked
layer). Nothing is normalized on your behalf. A raw `.f32` carries no
provenance: keep the converter's `.json` sidecar with it.

While a nonzero residual scale is active, session payloads and snapshots are
refused and the server does not open `--kv-disk-dir` (cache entries record no
steering identity; existing entries are left untouched). `/steer` and the live
FFN setter refuse a nonzero value on V4.1. `DS4_METAL_DISABLE_V41_RESIDUAL_STEERING=1`
turns the edit off, and a zero vector at any scale exercises the steered path
without changing anything: both are bitwise the unsteered run
(`make test-deepseek41-steering-admission`).

**Decaying the scale over tokens (`403`, experimental).** The residual scale can
decay from its start maximum (`--dir-steering-residual`) down to a residual
minimum (`--dir-steering-residual-decay-final`) over a window of generated tokens
(`--dir-steering-residual-decay-tokens`), easing the intervention off once the
refusal is broken in the first tokens. The curve is a cubic smoothstep run in
reverse: `scale = S - (S - F) * (3t^2 - 2t^3)`, `t = clamp(pos/N, 0, 1)`, so it is
S at the first in-phase token and holds at F past the window. The thinking phase
and the answer phase decay independently: `--dir-steering-think-residual-decay-tokens`
sets the thinking window (0 = reuse the answer window), the position resets at
`</think>` so the answer gets its own dose, and both phases share one start and
one final with the same vector. `decay-tokens 0` is a constant scale, bitwise the
`401` intervention. These flags are experimental under `403`; adoption as a
default is a separate measured decision (see `docs/steering-measurements.md`).
Scheduled steering runs one session at a time: a batched multi-session decode is
refused, since the one steering kernel applies a single scale per forward.

**Cost.** Measured 2026-10-13 on this tree, same build, steering off against
on (a unit direction at scale 4), fixed `--ssd-streaming-cache-experts 82GB`,
a 2K-token prompt and 256 generated tokens, ABAB x4 with one CLI process per
run: decode 24.3 -> 21.4 t/s (medians, -12%), prefill 72.3 -> 72.3 t/s
(unchanged). The cost is not the projection kernel but the fused HC
block-input kernels a steered layer has to skip: five dispatches per layer
instead of one. A fused steered variant would recover it; it is not part of
this change.

The FFN output is usually the best first target because it is late enough in
each layer to represent behavior, style, and topic signals. Attention steering
is available for experiments, but it can be more fragile.

The examples below use the FFN site. On V4.1 they refuse to start: without the
opt-in with upstream's line, with it because the FFN site is a V4 hook. They
document the tooling and the file format.

## Verbosity Example

The bundled example builds a style direction from 100 paired prompts. Each pair
asks for the same information in two ways:

- `examples/succinct.txt`: terse target prompts.
- `examples/verbose.txt`: detailed contrast prompts.

Because the extracted direction is `succinct - verbose`, negative FFN scales
make answers shorter, while positive FFN scales tend to make answers longer and
more explanatory.

Build the vector:

```sh
python3 dir-steering/tools/build_direction.py \
  --profile deepseek-v4-flash \
  --ds4 ./sf-ds4-1flash \
  --model deepseek-v4.1-flash.gguf \
  --good-file dir-steering/examples/succinct.txt \
  --bad-file dir-steering/examples/verbose.txt \
  --out dir-steering/out/verbosity.json \
  --component ffn_out \
  --ctx 512
```

This writes:

```text
dir-steering/out/verbosity.json
dir-steering/out/verbosity.f32
```

Try a terse run:

```sh
./sf-ds4-1flash -m deepseek-v4.1-flash.gguf --nothink --temp 0 -n 160 \
  --dir-steering-file dir-steering/out/verbosity.f32 \
  --dir-steering-ffn -1 \
  -p "Explain why databases use indexes."
```

Try a verbose run:

```sh
./sf-ds4-1flash -m deepseek-v4.1-flash.gguf --nothink --temp 0 -n 220 \
  --dir-steering-file dir-steering/out/verbosity.f32 \
  --dir-steering-ffn 2 \
  -p "Explain why databases use indexes."
```

The same vector can be used in either direction. The sign is the important part:

- negative scale amplifies the succinct target direction;
- positive scale suppresses that direction and usually gives the model more room
  to elaborate.

## Evaluating Scales

Use the sweep helper to test several strengths on a fixed prompt set:

```sh
python3 dir-steering/tools/run_sweep.py \
  --ds4 ./sf-ds4-1flash \
  --model deepseek-v4.1-flash.gguf \
  --direction dir-steering/out/verbosity.f32 \
  --prompts dir-steering/examples/eval_prompts.txt \
  --scales "-1,-0.5,0,0.5,1,2" \
  --tokens 180 \
  --nothink
```

Start with FFN scales between `-1` and `2`. If the model becomes repetitive,
ignores the prompt, or starts losing factual content, the scale is too strong.
For this example, `-1` is a good first terse setting and `2` is a good first
verbose setting. Strong negative scales such as `-2` or `-3` can over-amplify
the terse direction and collapse into repetition on some prompts.

## Observed Effect

With the 100-pair vector built from the commands above, local greedy checks
showed the expected behavior:

- Prompt: `Explain why databases use indexes.`
- `--dir-steering-ffn -1`: 67 words, one compact paragraph.
- `--dir-steering-ffn 0`: 136 words, structured explanation.
- `--dir-steering-ffn 1`: 140 words, structured explanation with more detail.

On a prompt that the unsteered model already answered briefly, positive steering
made the expansion more visible:

- Prompt: `What does DNS do?`
- `--dir-steering-ffn 0`: 44 words.
- `--dir-steering-ffn 2`: 171 words, with sections and step-by-step detail.

## Building Other Directions

The extractor compares two prompt sets:

- `good-file`: target prompts for the direction you want to represent.
- `bad-file`: contrast prompts that should be separated from the target.

It captures DS4 activations from the same local GPU graph used for inference,
averages target minus contrast, normalizes one vector per layer, and writes both
metadata JSON and the runtime `.f32` file.

Concept removal:

1. Put concept-heavy prompts in `good-file`.
2. Put neutral prompts in `bad-file`.
3. Run with a positive FFN scale.

Concept amplification:

1. Put desired concept prompts in `good-file`.
2. Put neutral prompts in `bad-file`.
3. Run with a negative FFN scale.

Style control:

1. Put prompts for the target style in `good-file`.
2. Put contrasting style prompts in `bad-file`.
3. Use negative scale to amplify the target style, positive scale to reduce it.

The method is not a fine-tune. It is a low-rank runtime edit, so it works best
for coarse behavior, topic, or style directions that are consistently present in
the activation captures.

## V4.1 control vectors and fusion

Two external V4.1 refusal directions are supported for the broad-removal work.
Both are single-stream, HC-collapsed residual directions for the same base model,
used **projectively** (`y -= scale*d*dot(d,y)`), never as weight edits.

- **Convert a GGUF control vector (401).** msuiche's control vector ships as a
  GGUF (`controlvector`, 39 `direction.N`). Convert it to the runtime `.f32`:

  ```sh
  python3 dir-steering/tools/controlvector_to_f32.py glp.deepseek-v41-flash-GLP-39-L1-39-a0.5.gguf \
    --out dir-steering/out/v41-msuiche.f32
  ```

  It validates the whole file first (exactly `direction.1..39`, F32 width 5120,
  consistent metadata, finite unit rows) and writes nothing on a refusal. The
  output is a 40x5120 `.f32` (layer 0 zeros, `direction.N` -> layer N) and a
  `.json` sidecar that records the source (hook `residual_stream_post_layer`,
  alpha 0.5, sha256, base revision) separately from the application site and
  intervention revision, and never calls the two equivalent. Apply it with
  `--dir-steering-residual` (see the V4.1 site above), never with
  `--dir-steering-ffn`, which V4.1 refuses.

- **Fuse msuiche with distributedcognition (404).** distributedcognition's
  `refusal_directions.pt` holds per-layer directions for the same model (read
  without torch). Fuse them per layer:

  ```sh
  python3 dir-steering/tools/fuse_directions.py \
    --msuiche dir-steering/out/v41-msuiche.f32 \
    --distcog refusal_directions.pt \
    --out dir-steering/out
  ```

  It sign-aligns and unit-norms each pair, searches a small layer offset (the two
  sites are one sub-layer apart; +1 aligns best on V4.1), and emits
  `v41-fused-denoise.f32` (`unit(a+b)`), `v41-fused-ortho.f32` (the orthogonal
  residual, a diagnostic), and `v41-fused-subspace_k1.f32`, each with a sidecar
  recording method, offset, per-layer cosine and provenance. Rank-k>1 subspace
  removal is not a single `.f32` (the runtime applies one direction per layer).

A fused candidate is **not validated until `402` has scored it** (refusal
removal, benign fidelity, over-refusal, capability, breadth). Keep the
lowest-rank candidate that beats msuiche-alone on refusal removal without
worsening the others; otherwise keep msuiche-alone. See
[refusal validation](../docs/REFUSAL_VALIDATION.md).
