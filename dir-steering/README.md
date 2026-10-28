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
--dir-steering-file-2 FILE  rank-2: a second direction file (should be orthogonal to the first)
--dir-steering-residual-2 F rank-2: constant scale for the second direction at the same site; default 0 (off)
--steering-profile NAME|FILE  one .sfsteer file (or a name in com-steering/profiles) with both slots' vectors, scales and think/answer gates; implies the V4.1 opt-in and replaces the options above
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
orthogonal to `d` per layer — `d2 = unit(b - (d.b)d)` — the two sequential removals equal projecting out their
2D span exactly, so the first direction's effect is untouched. Non-orthogonal
pairs still run, but compose as two rank-1 removals rather than a clean 2D
projection. The second slot has a constant scale, shares the opt-in and the disable env, and the persistence/KV guards apply when
either scale is nonzero. Motivation: one vector (rank-1) can only rotate the
removed direction; a second orthogonal direction adds a dimension, which is what
reaches refusals the single direction leaves (see `com-steering/result.md`).

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

**Think/answer gates.** Each slot can be gated to one reasoning phase, keyed on
the `<think>`/`</think>` boundary: it runs at its constant scale in that phase
and at 0 in the other. With the raw options the gates come from
`DS4_STEERING_THINK_PHASE` (slot 1) and `DS4_STEERING_THINK_PHASE2` (slot 2),
`think` or `answer`, default both; a steering profile carries its own. Gated
sessions decode one at a time: a native batched decode folds every row with one
session's scale, so the batch takes the serialized path.

**Steering profiles (`--steering-profile`).** A `.sfsteer` file holds a whole
steered configuration: the magic `SFSTEER1`, a little-endian uint32 header
length, a JSON header (`site`, `layers`, `width`, and per slot `scale`, `phase`
both|think|answer, plus provenance the engine ignores), then one 40x5120 f32
matrix per slot (one or two). The matrices go through the same validation as
plain direction files. A bare name resolves to
`com-steering/profiles/NAME.sfsteer`; an unknown name lists the profiles there.
`com-steering/make_profile.py` builds and shows them.

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

### Second direction (`412`)

`--dir-steering-file-2 FILE --dir-steering-residual-2 F` folds a second direction
at the same site, right after the first, with a constant scale. Same file format and the same
validation at engine open. A scale of 0, the default, leaves the second slot
unloaded, whatever file is named.

Order and angle decide what the pair does:

- **Orthogonal pair** (per-layer cosine near 0, e.g. an `ortho` fusion): at
  scale 1 each the two folds are an exact 2D removal, in either order.
- **Non-orthogonal pair** (msuiche against the abliteration vector, median
  |cos| 0.72): the second fold re-opens part of the first axis, so the order
  changes the result, and the pair over-doses the shared axis. After the two
  folds the second coordinate is zero and the first is not (the synthetic 0.72
  test asserts both), so the second flag is the one removed completely.

Engine open prints the median |cos| of the pair over the layers where both rows
are nonzero (`median |cos(d1,d2)| 0.722 over 39 layers` for msuiche +
abliteration; 0.0 for msuiche + its abliteration residual), and on the same line
the norm of the two folds composed in their plane (`409`) next to the larger
single fold `max(|1-F|, |1-G|, 1)`. The norm is how much the pair can amplify an
activation: an orthogonal pair equals the larger single fold at any scales, while
0.72 at 5 and 6 gives 15.03 against 5 (a rotation by 87.9 deg that leaves +8.44
on the first axis) and 0.22 at 7 and 6 gives 9.58 against 6, the two compositions
that re-closed the floor and broke breadth. When the norm is more than 20% above
the single fold the open also prints `warning: the two folds over-dose`; 0.22 at
7 and 2 (6.00 against 6) stays silent. The full in-plane operator for a pair is
the 2x2 composition of the two rank-1 folds in their shared plane, fixed by the
per-layer cosine and the two scales.

Off-path guarantee, checked by `make test-deepseek41-steering-rank2` (model
backed, 3 engine opens): the single-direction run, the same run with a second
file named at scale 0, and the same run with the second fold active on an
all-zero direction give bitwise equal logits, Engram history and KV state. The
model-less `make test` runs `test_deepseek41_graph --steering-rank2` (orthogonal
pair nulls both coordinates, `|dot|` under 1e-4, in either order; the 0.72 pair
is order dependent).

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

The broad-removal investigation used external V4.1 refusal directions. Both were
single-stream, HC-collapsed residual directions for the same base model, used
**projectively** (`y -= scale*d*dot(d,y)`), never as weight edits. The conversion
and fusion tools are not shipped (the investigation is closed); this records the
method so a direction can be rebuilt, and `com-steering/README.md` records the
directions the shipped `candor` profile ended up with.

- **GGUF control vector (401).** msuiche's control vector ships as a GGUF
  (`controlvector`, 39 `direction.N`, F32 width 5120). It converts to a 40x5120
  runtime `.f32` by mapping `direction.N` to layer N with layer 0 zeroed, after
  validating the whole file (exactly `direction.1..39`, consistent metadata,
  finite unit rows). Its source hook is `residual_stream_post_layer` at alpha 0.5
  — recorded separately from the application site and never called equivalent to
  it. Apply with `--dir-steering-residual`, never `--dir-steering-ffn` (V4.1
  refuses it).

- **Fusion with distributedcognition (404).** distributedcognition's
  `refusal_directions.pt` holds per-layer directions for the same model (readable
  without torch). Fusion sign-aligns and unit-norms each pair and searches a small
  layer offset — the two sites are one sub-layer apart, so **+1 aligns best on
  V4.1**. It yields `denoise = unit(a+b)`, an `ortho` residual (`unit(b-(a.b)a)`,
  a diagnostic and the orthogonal second slot), and a rank-1 subspace direction.
  Rank-k>1 subspace removal is not a single `.f32`: the runtime applies one
  direction per layer.

A fused candidate was **not validated until `402` scored it** (refusal removal,
benign fidelity, over-refusal, capability, breadth): keep the lowest-rank
candidate that beats msuiche-alone on refusal removal without worsening the
others, otherwise keep msuiche-alone. Results:
[com-steering/result.md](../com-steering/result.md).

## Quality gate after the steering series (`420`, 2026-10-28)

Evidence for the unsteered path after changes `400` to `419`. Tree `a4c61a4`
(engine files identical to `d7f9c95`), checkpoint
`DeepSeek-V4.1-Flash-1017-IQ2_XXS-Q2_K-imatrix.gguf`, `--ssd-streaming`, no
steering option on any run. Intervention identity of every steered result below:
site `v41_attn_input_weighted_fold_post_engram`, revision 2.

| Item | Command | Result |
|---|---|---|
| Model-less suite | `make test` | exit 0; the steering fold and file-validation tests it named at `401` (6.1) no longer exist, removed by `416`; the converter, geometry and mask self-checks still run and pass |
| Bitwise switches | `tests/test_deepseek41_graph <gguf> --decode-switch speed-bench/promessi_sposi.txt <env>` for `ROUTER_ONE`, `HC_BLOCK_INPUT`, `ROPE_QUANTIZE`, `EXPAND_FUSION`, `DECODE_PIPELINE_FAST_LOOKUP`, `READBACK_POLL`, `READBACK_SPLIT`, `READBACK_MAILBOX`, `GATHERED_KV_STAGE` and `RESIDUAL_STEERING` (no file) | 10 of 10: 65 exact logits, history and KV states at prefix 511 and 2047 |
| Steering state controls and routes | `make test-deepseek41-steering-admission`, `-routes` | not run: both targets and their tests were removed by `416` (`5406b3b`); the no-file control is covered by the `RESIDUAL_STEERING` row above |
| Parity | `SF_CHILD_DIR=<tree> SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash <gguf>` at `edc49c0`, upstream `fc80bd6` | PARITY OK, 10 of 10 prompts token-identical (`tools/parity/out/sf-ds4-1flash-20261027-180242`) |
| A/B, steering off | `speed-bench/ab_bench.py --a <7dea5e3> --b . --kinds all --bitwise`, in three invocations | tokens and logits bitwise; every kind has at least two valid pairs and none is below zero (row in `speed-bench/perf-record.md`) |

Steered results, as the series produced them (score = COMPLY + 0.3 DEFLECT over
the fixed 44 harmful-axis-a ids; `com-steering/result.md` has the rows):

| Result | Date | Phase | Score | Note |
|---|---|---|---|---|
| Overhead of an enabled fold, unit direction, scale 4 | 2026-10-13 (`401` 5.4) | decode | -12% t/s | the fused HC block-input kernels a steered layer skips; prefill unchanged |
| `msuiche-1017@7` baseline | 2026-10 | non-think | 26.7 `C24 D9 R11` | the baseline the candor profile beats |
| `equi-7` + `q1-7` constant | 2026-10-22/23 | non-think / think | 41.6 `C41 D2 R1` / 39.0 `C39 D0 R5` | think loops 17/44 at MT 8192; history |
| candor 418-C | 2026-10-25 | non-think / think | 41.3 `C41 D1 R2` / 39.0 `C39 D0 R5` | loop 11/44 at MT 8192 (13/44 at 12000); history after `420` |
| candor + `close2` (the shipped candor) | 2026-10-27 | think | 41.0 `C41 D0 R3` | loop 3/44 at MT 12000; non-think byte-identical to 418-C |

Not measured: the decode overhead of a steered session after `403` to `419`
(the closure channel adds an additive term in think only), and any `404`/`405`
number.

### Go / no-go

- **Go, unsteered path.** Bitwise exact on every documented switch, parity
  token-identical, A/B bitwise with no loss by kind. Nothing to fix.
- **Open, not a loss.** The two state-control targets named by the gate are gone;
  a later change that wants the admission and route tests back must restore
  them. The steered decode overhead after `419` is unmeasured.
