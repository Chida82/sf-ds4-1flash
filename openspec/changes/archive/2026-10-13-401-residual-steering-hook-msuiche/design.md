# Design

## Context

See proposal.md for motivation. This revision replaces the former sequence of contradictory site/index conclusions with one runtime contract. Source provenance is in `docs/upstream-prs.md`; the source cards' descriptions are not proof that a tensor in this engine has the same meaning.

The active graph is `ds41_gpu_graph`. `g->residual` carries four 5120-wide HC streams. Before attention, Engram updates this residual on layers 1 and 14; the preceding sublayer's mixer folds it into `g->x`. That weighted fold is transient: editing it affects attention, not directly every residual copy carried through HC expansion.

Already implemented: projection of `g->x` in the unfused decode path and `b->x` in ordinary batch prefill, direction upload/free, CLI/server residual scale and a disable switch. Still open: the two routes may place BF16 rounding on different sides of the projection (read from the source, not yet shown to matter); the batch branch of `ds41_decoder_prepare` omits steering; legacy active FFN/attention requests can be no-ops; persistent state has no steering identity (guarded by refusal, see D6).

### Historical evidence, not acceptance

The converter was run on the real source artifact: 819200 bytes, layer 0 zero and 39 unit rows. Prior notes report a scale-zero matching completion and a first-token screen: mean opener mass 0.986 at baseline and 0.971 at scale 0.5 on 25 prompts; a five-prompt sweep gave 0.851, 0.779, 0.567, 0.414 and 0.409 at scales 1, 2, 4, 8 and 16. Small benign checks were coherent through 8. Raw probe drivers were not retained in the repository. These are historical screening results, not state-level identity, a calibrated refusal rate, a confirmed hook index or a safe operating range. They stand as screening evidence; if D2's route-agreement test shows the rounding order matters, enabled-path numbers are remeasured under the new intervention revision.

## Goals / Non-Goals

**Goals:** an honest, testable fold edit; uniform intervention ordering on every route that produces its attention input; reliable files, errors and a safe answer for persistent state.

**Non-Goals:** equate the weighted fold with a mean-residual hook, choose the best scale/index/site, alter the baseline prefill schedule, add attention steering, enable distributed steering, full CPU V4.1 inference or a steering identity descriptor. `405` compares sites; `402` measures behavior.

## Decisions

### D1. Name source and application semantics separately

Keep the public `--dir-steering-residual` spelling. Identify the runtime site in metadata/reports as `v41_attn_input_weighted_fold_post_engram` with an intervention revision. Keep `source_hook=residual_stream_post_layer` when converting msuiche's artifact. They must never be presented as synonymous.

The source row `direction.N` stays row N; at the baseline runtime site row N applies before attention of layer N, for N=1..39. Layer 0 is zero. Source-to-runtime index searches and source-to-source fusion offsets are distinct experiments. Do not change runtime indexing based on cosine alone.

For unit d, `h' = h - alpha*d*dot(d,h)` leaves the component along d multiplied by `1-alpha`. Alpha 1 removes it; alpha 2 reflects it; 4 and 8 reverse and amplify it by factors 3 and 7. Negating d has no effect on a projective edit. A positive-versus-negative alpha experiment checks the intervention sign, not the vector's orientation. There is no validated nonzero default; the scale defaults to zero.

### D2. One enabled arithmetic order, decided by a test

The intended contract is the decode path's existing order:

```text
weighted fold --> existing BF16 rounding --> f32 projection --> RMSNorm --> existing norm-output BF16
```

First write the route-agreement fixture (D7): one synthetic folded row through the decode and the batch projection routes, outputs compared at an FP32 tolerance. If they differ beyond tolerance, move the batch fold rounding before the projection, without adding a second rounding between projection and normalization, and bump the intervention revision. If they agree within tolerance, record that and leave the arithmetic alone. With the edit disabled, preserve the original code and order either way. This is not permission to quantize anything new or change the baseline schedule.

In `ds41_hc_mix`, apply only on the attention side and continue to avoid fused fold-plus-norm paths when needed. Reuse `ds4_gpu_directional_steering_project_tensor`. In `ds41_before_attention_batch` and the batch branch of `ds41_decoder_prepare`, use the same pre-norm operation. A small shared application helper is appropriate if it prevents the reconstructed-key path from being omitted again; do not generalize the entire graph.

The non-batch decoder-prepare route already reaches `ds41_graph_before_attention`; do not apply twice. Review all callers and graph copies (`row = *g`) so directions, scale and views have the correct lifetime.

### D3. Cover recomputation, not just forward decode

`ds41_decoder_prepare` is used by decoder suffix publication/warming whenever the wide-sweep suffix optimization is active, not only deferred decoder execution above about 24.5K. Test ordinary 3072/4096/8192-token cases as well as a deferred-decoder case. Choose exact token counts through the graph test, not approximate word counts. Verify route coverage rather than assuming a context length selected the intended branch.

Keep the CPU path as reference. Add a model-less reference of the fold-edit-normalize operation and exercise it on synthetic rows; do not remove the CPU implementation or bypass the V4.1 CPU startup refusal. Where the CPU forward reference exposes the corresponding fold, mirror the residual edit with the same ordering, but do not describe this as complete CPU V4.1 support.

### D4. Validate files before use

The converter accepts exactly `direction.1` through `direction.39`, F32 width 5120, supported GGUF layout/version and consistent layer metadata. Reject duplicates, aliases, missing or extra rows, truncated/out-of-range storage, nonfinite values and non-unit rows outside the documented tolerance. Validate everything before writing either output. Make fixture directions distinguishable: the old fixture normalized every row to the same direction and could not detect a permutation.

The runtime consumes exactly 819200 bytes. Require finite scales in the frontend's supported range and finite rows, with row 0 zero and every other row either zero or unit within the same 1e-2 tolerance. Zero rows support controls and binary masks. Do not silently normalize user input: that would erase an unintended scaling error. A raw f32 file does not authenticate a source hook; document that limitation. The converter sidecar and `402` manifest record source/application hooks, revisions and content hashes; do not build a new general metadata parser in the engine merely to relabel the site.

### D5. Reject unsupported active sites

Keep the legacy flags/API/tooling. For an opted-in V4.1 session, nonzero FFN or attention scales must fail clearly. A file with the legacy implicit FFN=1 default must not pretend to steer; tell the user to select the residual site explicitly. `/steer` and its FFN setter must not report a successful V4.1 change that never reaches the graph. Requests that make no active change, such as a zero reset, may report the already-off state but never imply residual control.

Preserve the original no-opt-in refusal precedence from `400`. Do not add the whole steering block to bench as a side effect. `402` owns the minimum eval-driver plumbing needed for capability evaluation.

### D6. Refuse persistent state while steering is active

Steered activations make cached KV, text-prefix caches and snapshots configuration-specific. Rather than a versioned identity descriptor, the first implementation refuses the combination: with a nonzero residual scale, automatic persistent KV reuse (the server's lookups under its configured KV root) and explicit snapshot save/load fail before any session mutation, with one clear error naming the limitation. Zero-scale and off configurations keep today's caching unchanged. A steered session never reads, rewrites or deletes existing cache files.

The descriptor (site/intervention revision, index convention, scale bits, direction digest, disable state) is the follow-up for whoever first needs steered persistent state; `403` extends it then. Nothing here precludes it, and nothing here builds it.

### D7. Test mechanics separately from efficacy

Model-less/kernel checks: zero/unit/masked directions, distinguishable layers, one and multiple rows, invalid inputs, projection component factors, zero-vector control, the route-agreement fixture of D2, and ordering near BF16 boundaries. Compare an identical synthetic pre-normalization input through each hook route; use exact checks for no-ops and a documented FP32 reference tolerance where reduction order differs.

Model-backed controls: baseline; opt-in/no file; real vector at zero scale; zero vector at nonzero scale (forces the slow path); real vector with the disable switch set. Compare 65 decode steps of logits, KV and Engram. Text equality alone does not pass this gate.

Enabled coverage: short scalar prompt, batch prefill, short-wide suffix, 8K wide sweep, deferred decoder, append, and the refusal of snapshot save/load and persistent KV reuse while steered. Do not demand whole-model bitwise equality between inherently different upstream schedules; isolate the edit's contract and compare same-schedule runs. A failing zero-vector control is a numerical-path bug to resolve before behavior is measured.

Measure enabled prefill/decode cost with a fixed expert cache and record the command/identity. Enabled behavior intentionally changes; upstream parity is checked on the disabled path only.

### D8. Reconstructed rows fold with their carried split

`ds41_decoder_prepare` restores carried rows (`residual`, `pre`, `ffn_split`, selection, mask) into the batch workspace and, with batch attention off, loops over them with a row copy of the graph that re-aims only `residual` and `pre`; `ds41_graph_before_attention` folds every layer after the first with `row.ffn_split`, which that copy left pointing at the decode scratch. The batch branch reads the carried split and is exact, which is why the route test passed at 3072 and 4096 and failed only at 8192 under fixed arithmetic, unsteered too. One assignment re-aims `row.ffn_split` at the row's carried split. The default schedule never enters this branch, so its bits and speed are untouched; `--decoder-suffix` (upstream's test, the same switches) and the route test at 8192 are the evidence, and `420` closes the series with the unsteered guards.

## Risks / Trade-offs

- [Rounding alignment changes enabled answers] -> only if D2's test shows a difference; then bump the intervention revision and remeasure, otherwise nothing changes.
- [Steered runs lose persistent caching] -> a documented limitation; the guard is one check and the descriptor is the follow-up when someone needs it.
- [Source-hook mismatch remains] -> call this a baseline experiment, not a published replication; investigate in `405`.
- [Too many semantics in one graph helper] -> share only the pre-norm edit operation and its guard, not scheduling or HC routing.

## Migration Plan

Land input validation and tests, then the route-agreement test and any alignment it justifies, coverage, the persistent-state guard and integration checks. Update help, `dir-steering/README.md`, affected agent notes and source registry entries with each relevant step. Regenerate converted sidecars and re-run the disabled controls before enabling new behavior. Returning to scale zero restores unsteered computation and ordinary caching.
