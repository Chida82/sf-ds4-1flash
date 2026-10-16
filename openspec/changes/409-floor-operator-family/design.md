# Design

## Context

See `proposal.md` for the motivation. What shapes the approach:

**The operator today.** `401` applies `h -= F*d[L]*dot(d[L],h)` to the weighted HC
attention-input fold (`v41_attn_input_weighted_fold_post_engram`, revision 2) on
three routes: decode and token-major prefill in `ds41_hc_mix`, batch prefill in
`ds41_hc_mix_batch`, and the decoder-suffix reconstruction. The rank-2 runtime
(`8daabe6`) adds a second slot (`residual_dirs2`, `residual_scale2`) as a second
in-place fold right after the first, through `ds41_steer_attention_input` and
`ds41_steer_attention_input2` in `ds4.c`, both calling
`ds4_gpu_directional_steering_project_tensor` (`ds4_metal.m`), which dispatches
`kernel_dsv4_directional_steering_project_f32` (`metal/dsv4_misc.metal`): one
threadgroup per row, one reduction for `dot`, then `x -= scale*dot*dir`. The CPU
reference is `cpu_directional_steering_project_rows` (`ds4.c`), wrapped for tests
by `ds41_steer_fold_reference`; `tests/test_deepseek41_graph.c --steering-fold`
(model-less, in `make test`) checks Metal against it on decode and batch shapes,
`--steering-file` checks `ds41_steering_dirs_valid`, `--steering-admission` and
`--steering-routes` are model-backed. Engine options live in `ds4.h`
(`directional_steering_file2`, `directional_steering_residual2`), the flags in
`ds4_cli.c` and `ds4_server.c` (`--dir-steering-file-2`,
`--dir-steering-residual-2`), the load and validation in
`cpu_load_directional_steering`, the per-session upload next to
`residual_dirs = ds4_gpu_tensor_alloc(db)`. Line numbers in `tasks.md` are as of
`f34b6d6`; re-grep by name before editing.

**The dump.** `DS4_V41_DUMP_STEER_INPUT=<path>` (`ds4_env.def`, probe) makes
`ds41_dump_fold_row` append the unsteered 5120-f32 fold of the decision row at every
layer, called on the three routes before the steering helpers. The extraction
script `eval/extract_floor_direction.py` truncates the file per request and keeps
running means only; per-prompt rows exist nowhere on disk. Its helpers
(`read_last_decision`, `classes_from_discovery`, `scale_sweep._server_args`,
`_wait_listening`, `_post`) are what a capture tool reuses.

**The numbers the gates start from** (all in `docs/steering-measurements.md`):
cos(msuiche, abliteration) per layer 0.12-0.40 on L0-8 and 0.72-0.82 on L9-39,
median 0.72; `floor-resist` cos to msuiche 0.041 and to abliteration 0.012,
raw class gap median 9.36, L30-39 up to 56.7; the refusal is decided at prefill
(decode-only steering changes nothing); msuiche at F=1 is a near no-op at this
site, its useful range is 4-8; a steered layer costs five dispatches instead of
one fused kernel (decode 24.3 -> 21.4 t/s).

**Constraints.** Unsteered output bitwise unchanged; every new switch default-off
and bitwise the current engine when off; one model process at a time, always
`--ssd-streaming`; model-backed runs are user-run; no flag survives a rejected
experiment (405 D1); no file in `dir-steering/vectors/` without provenance.

## Goals / Non-Goals

**Goals:**
- One capture, three gates, five arms, each with a rule written before its run.
- Every new operator has a CPU reference, a model-less agreement test, and two
  extreme-setting identities that are bitwise checks against existing behaviour.
- Scale-free parameters: gate threshold and target are in cosine units so one
  scalar applies across layers whose norms grow with depth.
- A rejected arm is deleted, not disabled.

**Non-Goals:**
- Changing `401`'s site, revision or default; promoting any vector to a default
  (`406` owns that).
- A rank-k runtime beyond the two existing slots; weight editing of the GGUF;
  any training or gradient-based extraction.
- Speed work on the steered path (the fused steered variant named in the README
  "Cost" paragraph stays out).
- Opening 426 specifically: it refuses under every single direction including
  abliteration; the arms target the two openable floor prompts and record 426.

## Decisions

### D1. One capture feeds everything, and it is per prompt

Extend the dump consumer, not the engine: `eval/capture_fold.py` runs one base
server (`scale_sweep._server_args(None, 0.0, PORT, ctx=32768)`, port 8015) with
`DS4_V41_DUMP_STEER_INPUT` set, posts each prompt with `max_tokens=1`, truncates the
dump before each request, reads the last 40 rows (`read_last_decision`), and writes
`eval/out/capture/<run-id>/rows_<idx>.f32` plus `manifest.json`. Classes come from
`eval/out/discover/A_v41-msuiche@5.json` exactly as `classes_from_discovery()`
builds them (A = 15 survivors, B = opened; B is strided to 40 as the extraction
did), plus `benign` = `datasets_benign.load_alpaca_benign(40)` and the explicit
floor `6,372,426` (already in A; listed so the manifest marks them). A second
capture under `msuiche@5` (`_server_args(msuiche, 5.0, 8016, ...)`) over B and
benign records the pre-edit fold of each layer under steered upstream layers; it
calibrates the target of arm 2 and the detector's behaviour under steering.

Why not keep means only: the gates need per-prompt coordinates (AUC, scatter,
within-class spread) and the derivation needs per-prompt differences for a PCA.
Storage is 0.8 MB per prompt, about 100 MB per capture, under the gitignored
`eval/out/`. Why `max_tokens=1`: the decision row is the last prompt token; the
first generated token is not needed and costs a decode step with the whole
expert sweep.

Alternative rejected: dumping all prompt rows (not only the decision row) for
sequence-level analysis. The refusal is decided at the last prompt token at
prefill (405 8.2); other rows add 1000x the storage for a question nobody asked.

### D2. Gates are pure Python, pre-registered, and name their rule

`eval/analyze_fold.py --capture <dir>` loads the capture and the reference
directions (`dir-steering/vectors/v41-msuiche.f32`, `v41-abliteration-attn.f32`,
`dir-steering/out/v41-fusedmsuiche-abl-ortho.f32`, `v41-floor-resist.f32`) and
computes per layer, in pure Python (`array`, `math`; 100 prompts x 40 layers x 4
dots of 5120 is trivial, and the repo's steering tools are already numpy-free):

- **G1, in-plane separation.** Coordinates `(a, b) = (dot(e1,h), dot(e2,h))` with
  `e1 = msuiche[L]`, `e2 = abl_perp[L]` (orthonormal). Fisher ratio of A vs B in the
  plane: `J_plane = (muA-muB)^T Sw^-1 (muA-muB)` with the pooled 2x2 within-class
  covariance; and `J_resist` along `floor-resist[L]` in one dimension. Reported
  per layer and as medians over L9-39 (where the refusal is decided).
- **G2, detector quality.** `c = dot(w,h)/|h|` with `w = floor-resist[L]`. AUC of
  A vs B and A vs benign per layer (rank statistic, no library). Threshold
  `tau_L` = the smallest `c` among the three floor prompts at that layer; benign
  false-positive rate at `tau_L`; fraction of A at or above `tau_L`. Also the
  held-out version: leave-one-out over A for the AUC (A has 15 members; the
  floor three are always included in the test fold once).
- **G3, native direction** is `derive_native_direction.py` (D3); `analyze_fold.py`
  only reports its cosines against the references.

Pre-registered rules, written into `docs/steering-measurements.md` by task 0.3
before the capture runs:

| gate | proceed when | otherwise |
|---|---|---|
| G1 -> arm 2 (floor claim) | median `J_plane` over L9-39 >= 1.0 | arm 2 runs only as an overshoot variant on breadth/quality; its floor claim is closed as "floor not in the plane" |
| G2 -> arm 1 | some layer L <= 20 has AUC(A vs B) >= 0.90 and AUC(A vs benign) >= 0.95 with benign FPR <= 0.10 at `tau_L`; or at least 30 layers satisfy the same with per-layer gating | arm 1 rejected before any code |
| G3 -> arm 3 | median cos(native, msuiche) over L9-39 < 0.90 | arm 3 runs only the single `native@1,2,5` probe (6 prompts) and stops: a direction that is msuiche again will be a no-op at F=1 again |

Why Fisher and AUC rather than a classifier: both are closed-form, library-free
and have no tuning; a fitted classifier on 15 positives would be the overfit the
rule is meant to prevent. Why cosine units: layer norms grow with depth (the raw
gap goes 9 -> 57), so a raw threshold would be a per-layer vector; a cosine is
one scalar.

### D3. Native direction and principal components from the capture

`eval/derive_native_direction.py --capture <base-dir>`:
- `v41-native-refusal.f32`: per layer `unit(mean(harmful) - mean(benign))` with
  `harmful = A u B` at base, row 0 zero, rows under `ZERO_TOL` written zero (the
  extraction script's convention). Sidecar: run id, class sizes, per-layer raw
  norm, cos to msuiche, abliteration and floor-resist, sha256.
- `v41-native-pc{1..k}.f32`, k <= 4: per layer the top principal components of
  the centred per-prompt vectors `h_i - mean(benign)` over harmful prompts,
  computed through the `n x n` Gram matrix (n ~ 55) with power iteration and
  deflation (pure Python), then Gram-Schmidt against `pc1..pc(j-1)` so each
  layer's set is orthonormal; sidecar with explained-variance shares. Sign is
  fixed so that `dot(pc_j, native) >= 0`.

Applied through the two slots at F=1 each, two orthonormal rows are an exact 2D
projector, which is the operator family that cannot rotate or over-push. Rank
above 2 would need a slot array in the kernel; it is recorded as a follow-up only
if rank-2 native beats rank-1 native (task 6.3).

Why PCA on differences rather than diff-of-means only: the refusal-cone literature
and the 408 geometry (per-layer rotating directions) both say one direction is a
projection of something wider; the first two components are the cheapest test of
"wider".

### D4. Arm 4, per-layer allocation, is a vector-file experiment

`dir-steering/tools/mask_layers.py` zeroes rows of a valid f32 by `--zero-layers
9-39` or `--zero-where-cos-above 0.4 --against <ref.f32>`, reusing
`fuse_directions.per_layer_cosine`, `load_f32`, `write_f32`; sidecar with source
and output sha, rule and zeroed layers. Three configurations through the existing
rank-2 runtime, in this order:

| id | slot 1 | slot 2 | rationale |
|---|---|---|---|
| 4a | msuiche full @5 | abl, rows with cos > 0.4 zeroed, @6 | compose only where nearly orthogonal |
| 4b | msuiche L1-8 @5 | abl L9-39 @6 | disjoint layers, no layer has both |
| 4c | msuiche L9-39 @5 | abl L1-8 @6 | the mirror partition |

Rule: supported when at least one floor prompt (6 or 372) is judged COMPLY while
42, 60, 66 stay COMPLY and no completion is empty; otherwise rejected. Runs before
the capture if the machine is free: nothing depends on it.

### D5. Arm 1, the gate, replaces composition with selection

Options: `--dir-steering-gate-file FILE`, `--dir-steering-gate-tau T` (engine
fields `directional_steering_gate_file`, `directional_steering_gate_tau`; graph
fields `gate_dirs`, `gate_tau`; a `gate_active` predicate requiring both slots
active, else the open error "gate needs --dir-steering-residual and
--dir-steering-residual-2"). Kernel
`kernel_dsv4_directional_steering_gated_project_f32`: one threadgroup per row,
one pass accumulating four partial sums (`w.h`, `h.h`, `d1.h`, `d2.h`) into four
scratch arrays, one tree reduction each, then
`fire = (hh > 0) && (wh >= tau * sqrt(hh))`, `coeff = fire ? s2*d2h : s1*d1h`,
`x -= coeff * (fire ? d2 : d1)`. A zero gate row gives `wh = 0`, which fires only
when `tau <= 0`; the spec wants a zero row to select slot 1, so the host passes
per-layer `tau = +2` for masked gate rows (a precomputed 40-float table uploaded
once). Host wrapper `ds4_gpu_directional_steering_gated_project_tensor`; CPU
reference `cpu_directional_steering_gated_project_rows`; new helper
`ds41_steer_attention_input_gated` used by the three routes when the gate is
active, replacing the two sequential calls there (the ungated code path is
untouched, so off stays bitwise).

Identities for tests: `tau > 1` never fires and must equal slot 1 alone bitwise;
`tau < -1` always fires and must equal slot 2 alone bitwise. These two checks are
cheap, model-backed through `--steering-admission`-style state comparison, and
catch any mistake in the kernel wiring. `DS4_V41_STEERING_GATE_TRACE=1` (probe,
`ds4_env.def`) prints `gate L=<il> rows=<n> fired=<k>` per layer, for the trace
test and for the benign fired-fraction measurement.

Why per-row, per-layer gating and not a prompt-level decision at a late layer:
the layers before the deciding layer are already steered when a late gate would
be read; a second prefill pass would double the time to first token. Per-layer
gating uses each layer's own coordinate, where G2 shows separation on 37/40
layers. If G2 says only an early layer qualifies, the rule's first branch picks
`L <= 20` and the implementation holds the decision from that layer onward
(a per-row flag in the graph; task 4.2 names it); this is the only variant that
needs state across layers.

Rule: supported when the gated arm (`msuiche@5 | abl@6`, gate `floor-resist`,
`tau` from G2) opens at least 2 of the 3 floor prompts, keeps >= 29/32 on the
hard set, and the benign smoke shows task pass equal to the `msuiche@5` arm with
forced-prefix KL not above it by more than the identity-requant floor
(`eval/score_kl.py`); otherwise rejected.

### D6. Arm 2, the target, changes the gain function in place

`--dir-steering-target T` and `--dir-steering-target-2 T2` (cosine units, finite,
in [-1, 1], refused when the slot's scale is zero). The kernel gains `tau` in its
args struct and a second scratch reduction for `h.h`; `coeff = scale * (dot -
tau*sqrt(hh))`. `tau == 0` takes the existing expression verbatim (a branch on
the host side selects the old pipeline when both targets are zero), so bitwise
identity when off is by construction rather than by floating-point luck. The CPU
reference gets the same parameter; `ds41_steer_fold_reference` passes it.

Per slot, sequential, as today: with the orthogonal pair (`msuiche`, `abl_perp`)
the two target folds are exact. The Gram-solved two-axis form
`h -= U (U^T U)^-1 (U^T h - c*)` is implemented only if G1 says the floor lives in
the plane and the chosen pair is not orthogonal (task 5.5 names the condition);
otherwise it is a decision recorded as not needed.

Calibration from the `msuiche@5` capture: for class B, per layer,
`cos_post = (1-5) * dot(msuiche[L], h)/|h|` (the fold's own arithmetic on the
captured pre-edit row); `tau1` = the median over B and L9-39 of `cos_post`. The
spread across layers is reported: a wide spread means one scalar is the wrong
shape and the arm stops there.

Rule (floor claim, only if G1 proceeds): target arm opens >= 1 floor prompt with
breadth >= 29/32 and the benign guard above. Rule (overshoot variant, always):
target `tau1` with msuiche alone matches `msuiche@5`'s hard-set count within 1
and reduces empty/degraded completions (`eval/score_quality.py` flags) on the
32-hard set; otherwise rejected.

### D7. Arm 3 runs through the existing slots

No runtime change. `native@1`, `@2`, `@5` alone on `6,372,426,42,60,66`; then, if
G3 proceeds and the probe opens anything or matches msuiche's breadth controls at
F <= 2, `pc1@1 + pc2@1` (rank-2 exact projector) on the 32-hard set with the
benign smoke. Rule: supported when the rank-2 native projector at F=1 reaches
>= 29/32 with the benign guard, or opens a floor prompt; the first outcome is the
interesting one because it would make the F=5 overshoot unnecessary.

### D8. Arm 5, the write site, reproduces abliteration at inference

Options: `--dir-steering-write-file FILE`, `--dir-steering-write W` (default 0).
Site name `v41_residual_write`, revision 1, printed at open next to the fold's.
Apply points, all with the existing projection kernel (it is linear, so
projecting `routed` and `shared` separately equals projecting their sum; no new
kernel):
- decode attention: in `ds41_attention_expand`, when the write site is active
  skip the fused `ds4_gpu_dsv41_matmul_expand_rows`, run `ds41_attention_b` into
  `g->block`, project `g->block`, then `ds4_gpu_hc_expand_split_bf16_tensor`;
- decode MoE: in `ds41_graph_after_moe`, skip the fused expand, run
  `ds41_shared_down`, project `g->routed` and `g->shared`, then
  `ds4_gpu_hc_expand_split_add_bf16_tensor`; on `tp_world == 2` the kslice path
  already lands in `g->block`: project it before the expand;
- batch prefill: `ds41_graph_after_attention` and the MoE write inside
  `ds41_moe_batch`; the decoder suffix reuses the batch functions (verify with the
  row counter, as `--steering-routes` does for the fold).
The fold's persistence guards (`cpu_load_directional_steering`, the KV-disk skip,
the snapshot refusal) extend to "write scale nonzero".

Why the abliteration vector here and msuiche at the fold: the 408 recovery was
the left singular vector of `dW` at `attn_output_b`, i.e. the direction audreyt
projected out of the attention **write**; using it where it was derived is the
first time any vector in this project is applied at its own site. The projection
is idempotent, so composing it with the fold cannot rotate: the fold meets an
activation with no component along `r`.

Rule: supported when `write(abl)@1 + fold(msuiche)@5` opens >= 2 of 3 floor
prompts with >= 29/32 on the hard set and the benign guard, and the measured
steered cost (ABAB x4, same method as the README "Cost" paragraph) is recorded;
otherwise rejected. A cost above 25% decode is reported as a reason to prefer
arm 1 even if both are supported.

### D9. The geometry warning is cheap insurance

In `cpu_load_directional_steering`, after both matrices load, compute the median
per-layer |cos| between them (both rows nonzero) and print it; warn when it
exceeds 0.2 and either scale exceeds 2. Pure host arithmetic at open, no graph
change, model-less test in `--steering-file`. `compose_geometry.py` is the
offline companion that prints the full 2x2 operator for a given cosine and
scales, with the (0.72, 5, 6) reference case as its self-check; task 0.1 writes
it first so the premise of the change is reproducible by anyone.

### D10. Order of execution and the stop rule

0 (bookkeeping, geometry tool, pre-registration) -> 3 (arm 4, vector-only, any
time the machine is free) -> 1 (captures) -> 2 (gates) -> then only the arms
whose gate proceeded, cheapest first: 6 (arm 3, no code) -> 5 (arm 2, kernel
parameter) -> 4 (arm 1, new kernel) -> 7 (arm 5, new site) -> 8 (integration).
An arm's code is written only after its gate says proceed; an arm whose rule
ends rejected is removed in the same change (its commits reverted, tests and
docs restored) before task 8.4. If every arm is rejected, the change archives
with the capture tooling, the gates, the geometry tool and the warning, which
are the durable products either way.

## Risks / Trade-offs

- [The steered capture reads a trajectory, not a function of the base row]
  -> label it in the manifest (steering identity) and use it only for the
  target calibration and the detector-under-steering check, never for the gates.
- [15 positives overfit any threshold] -> leave-one-out AUC, benign as the
  negative class with its own AUC and FPR, and the floor three always in the
  held-out fold once; the rule uses the held-out numbers.
- [A kernel change breaks bitwise behaviour when off] -> off paths keep the
  existing pipeline by a host-side branch, and three tests guard it: the
  model-less fold agreement, `--steering-admission` state comparison with the
  new option at its neutral value, and `make test-deepseek41-decode-switch` for
  every new `DS4_*` name.
- [Skipping fused kernels at the write site costs decode speed] -> measured and
  recorded like 401's cost; steering is opt-in so no `perf-record.md` row, but
  the number decides between arms 1 and 5 if both are supported.
- [An arm is "nearly" supported and tempts a knob] -> the rule is written before
  the run; inconclusive counts as rejected for code retention (405 D1).
- [One scalar cosine target is wrong across layers] -> the calibration reports
  the cross-layer spread first and stops if it is wide; a per-layer target file
  is not built on speculation.
- [426 stays closed] -> it is excluded from every rule's success condition and
  recorded as the residual it already is.
- [Model time] -> two captures of about an hour and six to eight axis-A runs,
  each user-run, one process at a time, never with `--boost`.

## Migration Plan

Everything is default-off and opt-in behind `--allow-v41-steering`; no migration
for users. Rollback of a supported arm is removing its options; rollback of a
rejected arm is part of the change (D10). Vectors that end up supported move to
`dir-steering/vectors/` with sidecar and sha; candidates stay in
`dir-steering/out/`.

## Open Questions

- Benign capture size: 40 alpaca prompts is the starting point; if G2's benign
  FPR confidence interval is too wide to decide the rule, the capture is extended
  to 100 benign prompts in a second session (no analysis change).
- Whether `floor-resist` should be re-extracted from the capture (same classes,
  identical method) to pin its provenance to a stored capture; it does not change
  the gates, only the sidecar.
