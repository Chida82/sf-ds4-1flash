# Proposal

## Why

The broad refusal-removal project is achieved (`docs/steering-measurements.md`,
2026-10-16): `msuiche@5` opens 29/32 of the hard set and ~190/205 of the union,
`fused@7` gives 28/30 COMPLY. Three prompts, the floor `{6,372,426}`, resist every
direction and every combination tried at the V4.1 fold site. The last block
concludes "not openable by any constructed linear direction". That conclusion is
correct for the operator family that was tried, and the reason is geometric, not a
dose:

- the fold `h -= F*d*dot(d,h)` is a projection only at F=1. At the scales that work
  here (5-6) it is an **amplified reflection**: the coordinate along `d` becomes
  `(1-F)` times itself, -4 and -5;
- the rank-2 runtime applies the second fold after the first. Two reflections about
  axes at cos 0.72 (43.9 deg) compose into a **rotation by 87.9 deg** scaled by
  `sqrt((F-1)(G-1))` = 4.47 at (5,6). After both folds the activation's coordinate
  along msuiche is **+8.44** times its original value: far on the refusing side.
  That is the measured "msuiche@5 re-closes what abliteration@6 opened";
- the additive reading ("the shared component is removed twice") gives in-plane
  eigenvalues -8.5 and -0.5 instead: over-push on the shared axis, the empty
  completions seen on 372;
- two symmetric operators commute only when they share eigenvectors. With
  cos(msuiche, abliteration) = 0.72 and gains above 1, **no single fixed linear
  operator is at once "msuiche@5" on the breadth prompts and "abliteration@6" on
  the floor prompts**. The in-plane family `h -= U K U^T h` is closed by the
  measurements: K = diag(5,5) (`abl_perp`, flips the component abliteration keeps),
  the sequential product (rotation), and any least-squares compromise (both
  eigenvalues still beyond 2).

So the floor is not closed by the fold site; it is closed by *fixed linear
operators with gain at a single site*. Three exits remain and none has been
tried: make the operator depend on the input, change the gain function, or change
the basis/site. This change pre-registers five operator families along those
exits, with one shared prerequisite (a per-prompt capture of the fold) and three
offline gates that decide which families proceed before any model time is spent
on them. Each family ends with a supported/rejected/inconclusive record and a
runtime arm that is rejected leaves no flag behind.

## What Changes

- **Per-prompt capture of the fold** (`steering-activation-capture`, new): the
  existing `DS4_V41_DUMP_STEER_INPUT` dump keeps only running means in the
  extraction script. A capture tool saves the 40x5120 decision-row fold of every
  prompt with a manifest (class, index, prompt hash, steering identity). One base
  run over the 15 survivors, 40 opened, 40 benign and the floor feeds every
  offline gate; one `msuiche@5` run over the same prompts calibrates targets.
- **Three offline gates** (no model): in-plane separation of resistant vs opened
  prompts in `span(msuiche, abliteration)`; per-layer AUC of the `floor-resist`
  coordinate as a detector, with benign false-positive rate; a native
  harmful-vs-benign direction and its rank at the fold site. Decision rules are
  written down before the capture runs.
- **Arm 4, per-layer allocation** (vector files only, no code): the two directions
  interfere only in layers where cos > 0.4 (L9-39; L0-8 are 0.12-0.40). A mask
  tool zeroes rows by layer or by cosine threshold; three partitions run on the
  floor plus breadth controls through the existing rank-2 runtime.
- **Arm 1, conditional gate** (`directional-steering`, modified): a third
  direction file acts as a per-row detector in cosine units; above the threshold
  the second slot applies alone, below it the first slot applies alone. The
  non-commuting pair is never composed. Off is bitwise the current behaviour.
- **Arm 2, target fold** (`directional-steering`, modified): a per-slot target in
  cosine units, `coeff = F*(dot - tau*|h|)`, so the coordinate is set rather than
  multiplied: no overshoot on strong-refusal prompts, no under-push on weak ones.
  `tau = 0` is bitwise the current fold.
- **Arm 3, native rank-k projector**: a direction derived at the actual site from
  the capture (harmful vs benign), plus the top principal components of the
  per-prompt differences, orthonormal per layer, applied at F=1 through the
  existing two slots (an exact 2D projector). Rank above 2 is recorded as a
  follow-up, not built here.
- **Arm 5, residual-write projection site** (`directional-steering`, modified):
  the abliteration direction was recovered from `attn_output_b`, that is from the
  **write** side. Applying `out -= dot(r,out)*r` to the attention and MoE writes
  before they enter the HC streams reproduces an abliterated model at inference
  without touching weights, as an idempotent projection that neither reflects nor
  rotates; the fold then acts on an activation with no component along `r`.
- **Non-orthogonal rank-2 warning** (`directional-steering`, modified): with two
  active directions the engine prints the median per-layer cosine between them
  and warns when they do not commute at the given scales. This would have named
  the interference before the run that measured it.
- Bookkeeping: 405 tasks 4.1-4.5, 6A.3, 6A.4 and 7.1-7.3 are annotated as moved
  here; 405 keeps everything else.

Nothing here changes the unsteered path, the greedy output, or any default. Every
runtime addition is default-off and bitwise the current engine when off.

## Capabilities

### New Capabilities
- `steering-activation-capture`: per-prompt capture of the V4.1 attention-input
  fold at the decision position with a manifest, the offline analyses computed
  from it (in-plane separation, detector AUC, native direction and rank), and the
  pre-registered decision rules those analyses feed.

### Modified Capabilities
- `directional-steering`: a gated selection between the two residual slots in
  cosine units; a per-slot target that sets the coordinate instead of scaling it;
  a residual-write projection site on the attention and MoE outputs; a startup
  report of the composition geometry of two active directions. All default-off,
  all bitwise the current behaviour when off, all removed again if their arm is
  rejected.

## Impact

- `ds4.c`: the V4.1 fold helpers around `ds41_steer_attention_input*`, the
  `ds41_gpu_graph` steering fields, `cpu_load_directional_steering`, the engine
  option copy, the session upload, and for arm 5 the write sites
  (`ds41_attention_expand`, `ds41_graph_after_attention`, `ds41_graph_after_moe`
  and their batch and suffix analogues). CPU reference functions for every new
  operator so the model-less fold test keeps the Metal kernel honest.
- `metal/dsv4_misc.metal` and `ds4_metal.m`: the steering kernel gains a target
  term and a gated variant; the host wrapper gains the matching arguments.
- `ds4.h`, `ds4_cli.c`, `ds4_server.c`: new `--dir-steering-*` flags, help text.
- `ds4_env.def`: one line per new `DS4_*` name; `make env-check` enforces it.
- `tests/test_deepseek41_graph.c`, `tests/test_steering_admission.py`, Makefile
  test targets: fold-reference agreement for every new operator, identities at
  the extreme settings, route coverage for the write site, bitwise off paths.
- `eval/`: `capture_fold.py`, `analyze_fold.py`, `derive_native_direction.py`;
  `dir-steering/tools/mask_layers.py`, `compose_geometry.py`.
- Docs: `dir-steering/README.md`, `docs/steering-measurements.md` (append-only
  blocks), `AGENTS.md` Identity row, `dir-steering/vectors/README.md` for any
  vector promoted to the archive.
- Model time (user-run, one process at a time, always `--ssd-streaming`): two
  captures of about one hour each; per arm one or two axis-A runs of 6-35 prompts
  at 2048 tokens plus the benign smoke; the write-site cost measurement.
- Depends on `401` (fold, revision 2), the rank-2 runtime (`8daabe6`), `402`
  (axis-A harness, judge, KL and quality scorers), `408` (abliteration vector),
  the `floor-resist` extraction (`f70f42c`). `420` runs after this change's last
  code lands, as planned.
