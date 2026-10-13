# Directional Steering

Directional steering is a runtime activation edit for DS4. A steering file is a
flat `f32` matrix with one normalized hidden-width direction per normal
transformer layer. During inference, ds4 can apply the edit after attention
outputs, FFN outputs, or both:

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
`401`, [contract](../openspec/changes/401-residual-steering-hook-msuiche/specs/directional-steering/spec.md)).
`--dir-steering-ffn` and `--dir-steering-attn` are hooks of the older V4 graph,
which V4.1 never allocates: on this model they change nothing.

The tooling, the file format and the runtime options below are kept unchanged
(SPEC.md §B: steering stays in every child even where the model rejects it), so
a future model or an upstream change can use them without reinventing them.
The checked-in vector under `out/` was built for another model -- its shape is
`43 x 4096`, while this model is 40 layers of 5120 -- and is kept only as a
format example.

## Runtime Options

```text
--dir-steering-file FILE   load one f32 direction per normal model layer
--dir-steering-ffn F       apply steering after FFN outputs; default is 1 when a file is provided (no effect on V4.1)
--dir-steering-attn F      apply steering after attention outputs; default is 0 (no effect on V4.1)
--dir-steering-residual F  apply steering at the V4.1 post-HC-fold residual; default is 0
```

Effective scale at the residual site is ~4-8 for the msuiche vector, **not** its
published 0.5 alpha. Measured 2026-10-13 (first-token refusal probe): at 0.5 the
refusal is untouched (a near no-op), while 4 halves the first-token refusal mass and 8
roughly quarters it, with benign prompts still fully coherent. The 0.5 knee was msuiche's
value at their own application point (the residual that carries forward); this hook edits
the *transient* HC fold `g->x`, which is partly washed out, so it needs more magnitude for
the same downstream effect. Do not port 0.5 here.

Three application sites, each with its own scale, chosen to match the vector's own
derivation point:

| Site | Flag | For vectors derived at |
|---|---|---|
| FFN output (pre-residual) | `--dir-steering-ffn` | `ffn_out_pre_residual`-style vectors |
| Attention output | `--dir-steering-attn` | attention-output vectors |
| Post-HC-fold residual (V4.1) | `--dir-steering-residual` | `residual_stream_post_layer` control vectors (msuiche) |

A control vector is only valid at the site it was measured; msuiche's vector
(`residual_stream_post_layer`) is applied with `--dir-steering-residual`, and is wrong at
`--dir-steering-ffn`. Setting `--dir-steering-residual` does not auto-enable the FFN site.
(V4.1 residual steering currently covers the decode path; prefill/batch coverage and the
CPU reference are follow-ups.)

The FFN output is usually the best first target because it is late enough in
each layer to represent behavior, style, and topic signals. Attention steering
is available for experiments, but it can be more fragile.

The examples below use the FFN site. On V4.1 they refuse to start without the
opt-in and change nothing with it; they document the tooling and the file format.

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

  This writes a 40x5120 `.f32` (layer 0 zeros, `direction.N` -> layer N) and a
  `.json` sidecar carrying the hook, alpha, sha256, base revision and the
  non-monotone / L1-6 caveats. Its hook is `residual_stream_post_layer`, so it is
  applied at the residual site (change `401`), **not** at `--dir-steering-ffn`.

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
