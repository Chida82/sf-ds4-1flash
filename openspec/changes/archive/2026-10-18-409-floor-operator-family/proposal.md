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

Three measurements since the first draft of this change narrow the exits further
(`docs/steering-measurements.md`, 2026-10-16 and 2026-10-17):

- **The rank-1 rotation is negative.** `hybrid(α) = unit(msuiche + α·abl_perp)`
  loses breadth monotonically (6 and 21 keyword refusals of 32 at α 0.1 and 0.3,
  against msuiche@5's 3) and never moves the floor. No single direction in the
  msuiche/abliteration plane does both jobs.
- **A second axis exists and fails by dose, not by overlap.** `dealignai`
  (`dir-steering/vectors/v41-dealignai-wo.f32`, the FP8 weight diff of `wo_b` on
  layers 10-36, rank-1 share 0.80-0.96) has |cos| 0.22 to msuiche and 0.21 to
  audreyt: a genuinely different direction. Alone at 6 it opens exactly the two
  prompts the mark leaves, 23 and 27, and little else (7/30). Composed with
  `fused@7` as a second fold it breaks the fragile breadth prompts 1/13/16 and opens
  neither target at 6 (1/8, run `205628`); at 3 it opens 23 while 13/16 break
  (`231748`); 27 never opens in fusion. The dose that opens a target is the dose
  that re-breaks breadth, and no scale separates them.
- **The edit is two orthogonal tensors, and the second one is unreachable from the
  fold** (2026-10-17). A byte-diff of the dealignai checkpoint against stock over all
  40 layers shows the fine-tune touches exactly `attn.wo_b` and
  `ffn.shared_experts.w2`, layers 10-36, nothing else: the router
  (`gate.weight/bias/bias_vl`) and every sampled routed expert are identical, so the
  edit lives on the two always-on residual writes, not on expert selection. The
  `shared.w2` half, extracted the same way (`v41-dealignai-sharedw2.f32`, rank-1
  share 0.74-0.96), is a **fifth** direction: |cos| 0.03 to `wo_b` (the two halves
  are mutually orthogonal), ~-0.2 to the consensus, 0.88 residual after removing
  all of them. The `wo_b` half cannot be localized: no layer band opens 27 (lower
  10-23 kills the refusal keyword without complying at 6 and 9 and over-doses at
  12, upper 24-36 is inert, only the full span at 6 opens 23/27), and
  `fused@7 + wo_b[10-23]@6` holds 1/13/16 but leaves 27 closed. The `shared.w2`
  half is inert at the attention-input fold (6, 10, and shifted one layer): it is
  written at the end of the layer, and only a projection at that write can use it.

Both failures are visible before any run in one number: the norm of the composed
in-plane operator of two sequential folds, `(I - G d2 d2^T)(I - F d1 d1^T)`, against
the larger single fold `max(F-1, G-1)`:

| pair (cos; F, G) | composed norm | larger single fold | outcome |
|---|---|---|---|
| msuiche + audreyt (0.72; 5, 6) | 15.0 (rotation 87.9 deg, amplification 4.47) | 5 | floor re-closed |
| fused + dealignai (0.22; 7, 6) | 9.58 | 6 | 1/8, breadth broken |
| fused + dealignai (0.22; 7, 3) | 6.45 | 6 | 23 opens, 13/16 break |
| fused + dealignai (0.22; 7, 2) | 6.00 | 6 | untested (dose window) |
| fused + dealignai (0.22; 5, 4) | 5.0 | 4 | untested (dose window) |
| any pair at F = G = 1 (c; 1, 1) | c | 1 | contractive: projections |

A composition that out-gains its parts has been a failure every time; one that does
not (7, 3) still traded prompts, so the criterion excludes pairs without promising
any. The dose is bounded by construction only in two places: a target fold, which
sets the coordinate instead of multiplying it, and an F=1 projection at the write
site.

So the floor is not closed by the fold site; it is closed by *fixed linear
operators with gain at a single site*. Three exits remain and none has been
tried: make the operator depend on the input, change the gain function, or change
the basis/site. This change pre-registers five operator families along those
exits plus one vector-only dose window, with one shared prerequisite (a per-prompt
capture of the fold) and three offline gates that decide which families proceed
before any model time is spent on them. Each family ends with a
supported/rejected/inconclusive record and a runtime arm that is rejected leaves
no flag behind.

## What Changes

- **Per-prompt capture of the fold** (`steering-activation-capture`, new): the
  existing `DS4_V41_DUMP_STEER_INPUT` dump keeps only running means in the
  extraction script. A capture tool saves the 40x5120 decision-row fold of every
  prompt with a manifest (class, index, prompt hash, steering identity). One base
  run over the 15 survivors, 40 opened, the two dealignai-only prompts 23/27
  (class C), 40 benign and the floor feeds every offline gate; one `fused@7` run
  over the same prompts calibrates the composition with dealignai (a `msuiche@5`
  run is optional, for the msuiche-family overshoot variant only).
- **Three offline gates** (no model): separation of resistant vs opened prompts in
  `span(msuiche, abliteration)` and in the span of all four reference vectors
  (msuiche, audreyt, fused, dealignai; three dimensions, since fused lies in the
  first plane), with the dealignai coordinate of 23/27 plotted against the classes;
  per-layer AUC of the `floor-resist` coordinate as a detector, with benign
  false-positive rate; a native harmful-vs-benign direction, its rank at the fold
  site and its cosine to each of the four. Decision rules are written down before
  the capture runs.
- **Dose window** (vector files only, no code): `fused@7 + dealignai@2`,
  `fused@7 + dealignai@3` and `fused@5 + dealignai@4` on the eight indices of run
  `205628`. It is the gain-space baseline that arm 2 must beat, and the only
  composition family left below the contraction line.
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
  Its rank-2 form, fused at `tau1` and dealignai at `tau2` both at F=1, is the
  principled version of the dose window: the removed fraction is
  `sqrt(tau1^2 + tau2^2)` whatever the prompt. `tau = 0` is bitwise the current fold.
- **Arm 3, native rank-k projector**: a direction derived at the actual site from
  the capture (harmful vs benign), plus the top principal components of the
  per-prompt differences, orthonormal per layer, applied at F=1 through the
  existing two slots (an exact 2D projector). Rank above 2 is recorded as a
  follow-up, not built here.
- **Arm 5, residual-write projection site** (`directional-steering`, modified):
  both weight-diff directions were recovered from the attention **write**
  (`attn_output_b` for audreyt, `wo_b` layers 10-36 for dealignai). Applying
  `out -= dot(r,out)*r` to the attention and MoE writes before they enter the HC
  streams reproduces an abliterated model at inference without touching weights,
  as an idempotent projection that neither reflects nor rotates; the fold then
  acts on an activation with no component along `r`. The MoE write takes its own
  native direction through an optional `--dir-steering-write-moe-file`: the
  2026-10-17 byte-diff shows the edit's MoE half lives in `shared_experts.w2` and
  is orthogonal to the `wo_b` half, so the faithful reproduction projects the
  attention write along `wo_b` and the MoE write along `shared.w2`. Candidates:
  that per-site pair first, then abliteration, dealignai, and both attention
  directions as two sequential projections (composed norm 0.21, contractive), each
  with the fold at `fused@7` or `msuiche@5`.
- **Non-orthogonal rank-2 report** (`directional-steering`, modified): with two
  active directions the engine prints the median per-layer cosine between them
  and the norm of the composed in-plane operator, and warns when that norm exceeds
  the larger single fold by more than 20%. It would have named both failures above
  before the run that measured them.
- Bookkeeping: 405 tasks 4.1-4.5, 6A.3, 6A.4 and 7.1-7.3 are annotated as moved
  here; 405 keeps everything else. `v41-dealignai-wo.f32` gets its provenance row
  and sha256 in `dir-steering/vectors/README.md` (today the file is untracked and
  has no row).

Nothing here changes the unsteered path, the greedy output, or any default. Every
runtime addition is default-off and bitwise the current engine when off.

## Capabilities

### New Capabilities
- `steering-activation-capture`: per-prompt capture of the V4.1 attention-input
  fold at the decision position with a manifest, the offline analyses computed
  from it (separation in the span of the reference directions, detector AUC,
  native direction and rank), and the pre-registered decision rules those analyses
  feed.

### Modified Capabilities
- `directional-steering`: a gated selection between the two residual slots in
  cosine units; a per-slot target that sets the coordinate instead of scaling it;
  a residual-write projection site on the attention and MoE outputs; a startup
  report of the composition geometry of two active directions, with a dose
  warning. All default-off, all bitwise the current behaviour when off, all
  removed again if their arm is rejected.

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
  the extreme settings, route coverage for the write site, bitwise off paths, the
  geometry report at (0.22; 7, 6).
- `eval/`: `capture_fold.py`, `analyze_fold.py`, `derive_native_direction.py`;
  `discover.run_config` and `hybrid_phaseb.py` extended with extra server
  arguments so rank-2, gate, target and write arms run on the server path;
  `dir-steering/tools/mask_layers.py`, `compose_geometry.py`.
- **Acceptance metre per vector family, re-projection, full re-test.** Each arm is
  measured against the high-water mark of its vector family
  (`docs/REFUSAL_VALIDATION.md`): `fused@7` arms against 28/30 on `union[:30]`,
  2048 tokens, judge base; `msuiche@5` arms against 29/32 on the hard set plus the
  floor. A subset result is re-projected onto the full set before comparison. A
  new vector (dealignai), a new site (the write site) or a lower scale breaks
  carry-forward: the claim needs the full `union[:30]`, not a subset.
- **Two generation paths.** The CLI (`eval/run.py`) and the server
  (`/v1/chat/completions`) give different greedy trajectories for the same vector,
  scale and prompt. The capture is a server-path measurement, so arms whose
  parameters are calibrated from it (gate threshold, targets) are screened on the
  server path; the CLI judge confirmation is reported apart. Arms without
  calibrated parameters (dose window, arm 4, write site) go to the CLI judge
  directly, where the mark lives. No table mixes the two paths.
- Docs: `dir-steering/README.md`, `docs/steering-measurements.md` (append-only
  blocks), `AGENTS.md` Identity row, `dir-steering/vectors/README.md` (dealignai
  row now; any vector promoted to the archive later).
- Model time (user-run, one process at a time, always `--ssd-streaming`): two
  captures of about one hour each; the dose window (three runs of eight prompts);
  per arm one or two axis-A runs of 6-35 prompts at 2048 tokens plus the benign
  smoke; a full `union[:30]` for every configuration that passes its eight-prompt
  screen; the write-site cost measurement.
- Depends on `401` (fold, revision 2), the rank-2 runtime (`8daabe6`), `402`
  (axis-A harness, judge, KL and quality scorers), `408` (abliteration vector),
  the dealignai recovery (`ec1b5c3`), the `floor-resist` extraction (`f70f42c`).
  `420` runs after this change's last code lands, as planned.
