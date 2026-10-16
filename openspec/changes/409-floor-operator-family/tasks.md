# Tasks

Conventions for every task below. Line numbers are as of `f34b6d6`; always re-grep
by the quoted name before editing. Model-backed steps are **user-run**: prepare the
exact command, hand it over, and read the output file; never launch a model while
another run may be active. Every model command carries `--ssd-streaming`; never add
`--boost`. "Bitwise" means logits, KV state and Engram history compared the way
`tests/test_deepseek41_graph.c --steering-admission` compares them. Nothing is
committed or pushed by these tasks; staging is fine. Decision rules are the ones in
`design.md` D2, D4-D8 and must be copied into the measurements log by task 0.3
*before* task 3.2 runs.

## 0. Pre-registration and bookkeeping

- [ ] 0.1 Write `dir-steering/tools/compose_geometry.py` (pure Python, no numpy):
  `--cos C --f F --g G` prints, in the plane of two unit directions at cosine C, the
  2x2 operator of the sequential folds `(I - G d2 d2^T)(I - F d1 d1^T)` and of the
  additive form `I - F d1 d1^T - G d2 d2^T`: the coefficient left on the d1
  component (`M[0][0]`), the eigenvalues (or, when complex, the rotation angle
  `2*acos(C)` and the amplification `sqrt(det)`), for both forms. `--self-check`
  asserts the reference case `--cos 0.72 --f 5 --g 6`: sequential `M[0][0]` = 8.44,
  amplification 4.47, angle 87.9 deg; additive eigenvalues -8.48 and -0.52, all
  within 0.01. Verify: `python3 dir-steering/tools/compose_geometry.py --self-check`
  prints `ok` and exits 0; add that line to the `test:` recipe next to
  `controlvector_to_f32.py --self-check` (Makefile ~437) and check
  `make -n test | grep compose_geometry` shows it.
- [ ] 0.2 Annotate `openspec/changes/405-steering-investigations/tasks.md`: append
  " — moved to 409 (task 5.x / 6.x / 7.x / 8.x)" to tasks 4.1-4.5 (native
  direction -> 409 group 4-5), 6A.3 and 6A.4 (overshoot cap -> 409 group 6), and
  7.1-7.3 (attention channel -> 409 group 8). Do not tick them. Verify:
  `grep -c 'moved to 409' openspec/changes/405-steering-investigations/tasks.md`
  prints 10.
- [ ] 0.3 Append a dated block at the top of `docs/steering-measurements.md` titled
  "409 pre-registration" containing: the geometry paragraph from `proposal.md`
  (the four numbers), the three gate rules and the five arm rules exactly as in
  `design.md` D2, D4-D8 (tables copied verbatim), the capture plan (classes and
  sizes), and the sentence "rules are fixed before the capture; an arm whose rule
  ends rejected or inconclusive is removed". Verify: the block is the first `##`
  after the conventions, and `grep -n 'J_plane\|AUC(A vs B)\|29/32' docs/steering-measurements.md`
  finds the rules inside it.

## 1. Composition geometry warning at engine open (D9)

- [ ] 1.1 In `ds4.c` `cpu_load_directional_steering` (~26076), after
  `directional_steering_dirs2` loads: compute over layers where both rows are
  nonzero the per-layer |cos| between `directional_steering_dirs` and `dirs2`
  (plain double loops over `DS4_N_EMBD`), take the median, and print
  `ds4: V4.1 residual steering rank-2: median |cos(d1,d2)| %.3f over %u layers`;
  when the median > 0.2 and (`residual_scale` > 2 or `residual2_scale` > 2) also
  print `ds4: warning: the two folds do not commute at these scales; sequential
  folds compose as a rotation (see dir-steering/README.md, Rank-2)`. No graph or
  kernel change. Verify: build clean, `make test` green.
- [ ] 1.2 Extend `tests/test_deepseek41_graph.c check_steering_file` (~2750): write
  two matrices, one pair orthogonal, one at cos 0.72 (build row 2 as
  `0.72*row1 + 0.694*unit_perp`), load both as slots 1 and 2 at scales 5 and 6
  through `cpu_load_directional_steering`, capture stderr, and REQUIRE the median
  line shows about 0.000 without the warning for the first pair and about 0.720
  with the warning for the second. Verify: `./tests/test_deepseek41_graph
  --steering-file` prints the existing PASS line plus `rank-2 geometry report:
  orthogonal silent, cos 0.72 warned`.
- [ ] 1.3 Document the report in `dir-steering/README.md` Rank-2 paragraph (~83):
  two sentences, what is printed and what the warning means, with the 2x2
  numbers from `compose_geometry.py`. Verify: `grep -n 'do not commute' dir-steering/README.md`.

## 2. Arm 4: per-layer allocation (vector files only, D4)

- [ ] 2.1 Write `dir-steering/tools/mask_layers.py` reusing `fuse_directions.load_f32`,
  `write_f32`, `per_layer_cosine`, `unit`: `--in F --out G` with either
  `--zero-layers 9-39,0` (ranges and singles) or `--zero-where-cos-above 0.4
  --against REF.f32`; write `G` and `G.json` (source sha256, rule, zeroed layers
  with their cosines when the rule is cosine, output sha256). `--self-check`
  builds a random valid matrix, masks 9-39, asserts those rows are zero and rows
  1-8 are byte-identical, then asserts the cosine rule zeroes exactly the planted
  layers. Verify: `python3 dir-steering/tools/mask_layers.py --self-check` prints
  `ok`; add the line to the `test:` recipe (see 0.1) and confirm with `make -n test`.
- [ ] 2.2 Build the three configurations into `dir-steering/out/`:
  `v41-abl-cos-le-0.4.f32` (abliteration, `--zero-where-cos-above 0.4 --against
  dir-steering/vectors/v41-msuiche.f32`), `v41-msuiche-L1-8.f32` (`--zero-layers
  9-39`), `v41-msuiche-L9-39.f32` (`--zero-layers 1-8`), `v41-abl-L9-39.f32`,
  `v41-abl-L1-8.f32`. Verify each with the engine's validator through the model-less
  file test path: `./tests/test_deepseek41_graph --steering-file` is generic, so
  instead run `python3 - <<EOF` that reads each file and checks 40x5120 f32,
  row 0 zero, other rows unit or zero; print the sidecar's zeroed-layer list for
  each and record the lists in the task's measurement block.
- [ ] 2.3 **User-run.** Three axis-A runs, `--indices 6,372,426,42,60,66
  --max-tokens 2048 --judge base`, port as `eval/run.py` chooses:
  4a `--steer dir-steering/vectors/v41-msuiche.f32 --residual 5 --steer2
  dir-steering/out/v41-abl-cos-le-0.4.f32 --residual2 6`;
  4b `--steer dir-steering/out/v41-msuiche-L1-8.f32 --residual 5 --steer2
  dir-steering/out/v41-abl-L9-39.f32 --residual2 6`;
  4c `--steer dir-steering/out/v41-msuiche-L9-39.f32 --residual 5 --steer2
  dir-steering/out/v41-abl-L1-8.f32 --residual2 6`. Note the geometry line each
  run prints (1.1). Verify: three run directories under `eval/out/` with six
  judged completions each; append one dated block to `docs/steering-measurements.md`
  with the 6x3 table (idx, base, 4a, 4b, 4c, word counts) and the D4 rule's
  verdict per configuration.

## 3. Per-prompt capture (D1)

- [ ] 3.1 Write `eval/capture_fold.py` next to `extract_floor_direction.py`,
  importing its `read_last_decision`, `build_union`, `classes_from_discovery` and
  `scale_sweep._server_args/_wait_listening/_post`. Arguments: `--out DIR`
  (default `eval/out/capture/<YYYYmmdd-HHMMSS>`), `--port` (default 8015),
  `--steer F --residual S` (optional, forwarded to `_server_args`), `--classes
  A,B,benign,floor` (default all), `--b-count 40`, `--benign-count 40`,
  `--dry-run`, `--self-check`. Manifest `manifest.json`: run id, server argv,
  steering identity (`none` or `{file, sha256, residual}`), code commit
  (`git rev-parse HEAD`), and per prompt `{idx, class, source, text_sha256,
  file, file_sha256, rows_in_dump, error}`. Per prompt: truncate the dump, POST
  with `max_tokens=1`, read the last 40 rows (reject and record `error` when the
  row count is not a positive multiple of 40), write `rows_<idx>.f32`
  (819200 bytes). Benign class: `datasets_benign.load_alpaca_benign(count)`,
  indices prefixed `b` in the manifest so they cannot collide with union indices.
  `--self-check`: synthesize a dump of 80 rows, assert the last 40 are returned,
  assert a 41-row dump is rejected, assert the manifest round-trips. Verify:
  `python3 eval/capture_fold.py --self-check` prints `ok`; `--dry-run` prints
  `A 15 · B 40 · benign 40 · floor 3 (in A)`, the argv and the out dir; add the
  self-check line to the `test:` recipe (see 0.1).
- [ ] 3.2 **User-run.** Base capture: `nohup caffeinate -i python3 eval/capture_fold.py
  --out eval/out/capture/base > eval/out/capture/base.log 2>&1 &`. Expect about
  one prefill per prompt plus the server open. Verify: `manifest.json` lists 95
  entries (15 + 40 + 40) with `error` null, 95 files of 819200 bytes
  (`find eval/out/capture/base -name 'rows_*.f32' -size 819200c | wc -l` = 95),
  and `rows_6`, `rows_372`, `rows_426` are present with class `A`.
- [ ] 3.3 **User-run.** Steered capture for calibration: same command with
  `--steer dir-steering/vectors/v41-msuiche.f32 --residual 5 --classes B,benign
  --port 8016 --out eval/out/capture/msuiche5`. Verify: 80 entries, manifest
  steering identity names the msuiche sha256 and residual 5.0, server log shows
  the `V4.1 residual steering` open line.

## 4. Offline gates and native derivation (D2, D3)

- [ ] 4.1 Write `eval/analyze_fold.py --capture DIR [--out report.json]` (pure
  Python). Loads the reference f32s (`dir-steering/vectors/v41-msuiche.f32`,
  `dir-steering/vectors/v41-abliteration-attn.f32`,
  `dir-steering/out/v41-fusedmsuiche-abl-ortho.f32`,
  `dir-steering/out/v41-floor-resist.f32`). Per layer 1-39: G1 `J_plane` (2D Fisher
  ratio of A vs B in the `(msuiche, abl_perp)` basis, pooled within-class 2x2
  covariance, invert by hand, add 1e-9 to the diagonal) and `J_resist` (1D along
  floor-resist); G2 `c = dot(w,h)/|h|`, AUC A vs B and A vs benign (rank
  statistic), `tau_L` = min `c` over idx 6/372/426, benign FPR at `tau_L`, A
  recall at `tau_L`, leave-one-out AUC over A. Summary: medians over L9-39, the
  G1 and G2 rule verdicts (copy the thresholds from `design.md` D2 into constants
  at the top of the file), the proposed `(L*, tau)` for arm 1 (first branch: the
  smallest L <= 20 passing; second branch: the count of passing layers), and a
  markdown table for the measurements log. `--self-check`: synthesize two Gaussian
  classes with a planted separating direction in 5120-d, assert AUC along it
  >= 0.97 and along a random unit direction within 0.5 +- 0.1, assert `J_plane`
  recovers a planted 2D offset. Verify: `python3 eval/analyze_fold.py --self-check`
  prints `ok`; add to the `test:` recipe (see 0.1).
- [ ] 4.2 Write `eval/derive_native_direction.py --capture eval/out/capture/base
  --out-dir dir-steering/out [--k 2]`: `v41-native-refusal.f32` = per layer
  `unit(mean(A u B) - mean(benign))`, row 0 zero, rows with raw norm < 1e-6 zero;
  `v41-native-pc1.f32 .. pcK.f32` from the Gram matrix of the centred harmful
  rows (`h_i - mean(benign)`), power iteration (200 steps, tolerance 1e-9) with
  deflation, per-layer Gram-Schmidt so `pc1..pcK` are orthonormal per layer,
  sign so that `dot(pc_j, native) >= 0`. Sidecars: capture run id, class sizes,
  per-layer raw norm, per-layer cos to msuiche / abliteration / floor-resist,
  explained-variance share per component, sha256 of each output. `--self-check`:
  plant a direction and a 2D spread in synthetic rows, assert cos >= 0.99 for the
  native direction and for `pc1`, assert `pc1 . pc2` = 0 within 1e-6, assert two
  runs give identical bytes. Verify: `python3 eval/derive_native_direction.py
  --self-check` prints `ok`; add to the `test:` recipe (see 0.1).
- [ ] 4.3 Run the gates on the base capture (no model):
  `python3 eval/analyze_fold.py --capture eval/out/capture/base --out
  eval/out/capture/base/report.json` and `python3 eval/derive_native_direction.py
  --capture eval/out/capture/base --out-dir dir-steering/out --k 2`; then
  `python3 eval/analyze_fold.py --capture eval/out/capture/base --native
  dir-steering/out/v41-native-refusal.f32` to add the G3 cosines. Append one dated
  block to `docs/steering-measurements.md` with the per-layer table (L, J_plane,
  J_resist, AUC A/B, AUC A/benign, FPR, recall, LOO AUC), the medians, the G1/G2/G3
  verdicts in the pre-registered words, and the `(L*, tau)` proposal. Verify: the
  block names which of groups 5, 6, 7 proceed and which stop; `report.json` exists.
- [ ] 4.4 Calibrate the arm-2 target from the steered capture: add
  `--target-from eval/out/capture/msuiche5 --direction dir-steering/vectors/v41-msuiche.f32
  --scale 5` to `analyze_fold.py`, computing per layer and over class B
  `cos_post = (1 - scale) * dot(d,h)/|h|`, its median and interquartile range per
  layer and over L9-39, and the proposed `tau1`. Record the spread in the same
  measurements block (4.3) and state whether one scalar is acceptable (IQR over
  L9-39 below half the median's magnitude) or the arm stops. Verify: the block
  shows `tau1` and the IQR.

## 5. Arm 3: native direction through the existing slots (D7; only the probe if G3 stops)

- [ ] 5.1 **User-run.** Probe: three axis-A runs on `--indices 6,372,426,42,60,66
  --max-tokens 2048 --judge base` with `--steer dir-steering/out/v41-native-refusal.f32
  --residual 1`, `--residual 2`, `--residual 5`. Verify: 6x3 table appended to
  the measurements log with word counts and the D7 reading (opens a floor prompt?
  matches msuiche@5 on 42/60/66 at F <= 2?).
- [ ] 5.2 **User-run, only if 5.1 passes the D7 probe condition and G3 proceeded.**
  Rank-2 native projector `--steer dir-steering/out/v41-native-pc1.f32 --residual 1
  --steer2 dir-steering/out/v41-native-pc2.f32 --residual2 1` on the 32-hard set
  (the phase-B indices of `eval/out/discover`, listed in the 2026-10-16 "broad
  vector×scale screen" block) and `--suite benign-smoke`; note the geometry line
  reports |cos| about 0 (orthonormal). Verify: measurements block with the 32-row
  table, the count against 29/32, the benign KPIs against the `msuiche@5` arm,
  and the D7 verdict.
- [ ] 5.3 Record the rank>2 decision in the measurements block: "follow-up change
  needed" only if 5.2 beat 5.1's best; otherwise "not needed". Verify: the
  sentence exists; no slot-array code is written in this change.

## 6. Arm 2: target fold (D6; floor claim only if G1 proceeded, overshoot variant always)

- [ ] 6.1 Options and plumbing. `ds4.h` (~148): add `float directional_steering_target;`
  and `float directional_steering_target2;` with `/* sf: 409 */` comments.
  `ds4_cli.c` (~2019) and `ds4_server.c` (~14487): add `--dir-steering-target` and
  `--dir-steering-target-2` parsed with `parse_float_range(..., -1.0f, 1.0f)`
  next to `--dir-steering-residual-2`, help text "target cosine the slot's
  coordinate is set toward; 0 = scale only". Engine struct (~25827): matching
  fields; option copy (~30432-30452): copy both; `cpu_load_directional_steering`
  (~26076): refuse non-finite, refuse a nonzero target whose slot scale is zero
  with `ds4: --dir-steering-target needs a nonzero --dir-steering-residual`
  (and the `-2` pair). Graph struct (~23170): `float residual_tau, residual_tau2;`
  set at session upload (~31897, ~31928). Verify: build clean; `./sf-ds4-1flash
  --help | grep -c dir-steering-target` prints 2; same for the server.
- [ ] 6.2 Kernel and references. `metal/dsv4_misc.metal`
  `ds4_metal_args_dsv4_directional_steering_project` (~392): add `float tau;`.
  In `kernel_dsv4_directional_steering_project_f32` (~406): accumulate `hh` in a
  second scratch array (`scratch + n_threads`) alongside `sum`, reduce both, then
  `coeff = args.tau == 0.0f ? args.scale * dot : args.scale * (dot - args.tau *
  sqrt(hh))`. `ds4_metal.m` `ds4_gpu_directional_steering_project_tensor` (~29758):
  add a `float tau` parameter, pass it in args, double the threadgroup scratch
  allocation. `ds4.c`: add `tau` to `cpu_directional_steering_project_rows`
  (decl ~1340, definition by name) with the same two-branch expression, to
  `ds41_steer_fold_reference` (~26028), and pass `g->residual_tau` /
  `g->residual_tau2` from `ds41_steer_attention_input` / `..._input2` (~23594,
  ~23609). Every other caller passes `0.0f`. Verify: build clean; `make test`
  green with the existing `--steering-fold` output unchanged (tau 0 path).
- [ ] 6.3 Tests. In `check_steering_fold` (~2611): add cases with `tau` in
  {-0.3, 0.2} on decode (1 row) and batch (ROWS) shapes, Metal vs
  `ds41_steer_fold_reference` within the existing tolerance; add the "coordinate
  set" check: unit direction, scale 1, `tau` = -0.25, rows of norms 1, 10, 100,
  REQUIRE `dot(d, x_after)/|x_after|` within 1e-3 of -0.25. In
  `check_steering_admission` (~2808): add a configuration with `--dir-steering-target 0`
  and REQUIRE bitwise equality with the configuration without it; in
  `check_steering_file` REQUIRE that target 0.2 with residual scale 0 is refused.
  Update `tests/test_steering_admission.py` with one CLI case `--dir-steering-target 1.5`
  expecting the range error. Verify: `./tests/test_deepseek41_graph --steering-fold`
  prints a line naming the target cases; `make test-deepseek41-steering-admission`
  PASS (user-run, model-backed).
- [ ] 6.4 Docs and registry. `dir-steering/README.md` flag table (~50) and the V4.1
  site section: the formula `coeff = F*(dot - tau*|h|)`, "tau 0 is bitwise the
  scale-only fold", calibration from the capture. `AGENTS.md` Identity Steering
  row: one clause. No new `DS4_*` name, so `ds4_env.def` is unchanged; verify
  `make env-check` still passes. Verify: `grep -n 'dir-steering-target' dir-steering/README.md AGENTS.md`.
- [ ] 6.5 Add `--target T --target2 T` to `eval/run.py` mirroring how `--steer2 /
  --residual2` reach the server argv (~345, ~358, ~486-544), with the same
  validation style (`--target` needs `--steer`). Verify: `python3 eval/run.py
  --self-check` passes and `--dry-run`-style argv shows the new flags.
- [ ] 6.6 **User-run.** Overshoot variant (always): `--steer v41-msuiche.f32
  --residual 5 --target <tau1 from 4.4>` on the 32-hard set and `--suite
  benign-smoke`, against the stored `msuiche@5` arm; run `eval/score_quality.py`
  on both. Floor claim (only if G1 proceeded): the same on
  `--indices 6,372,426,42,60,66`, and rank-2 targets with `--steer2
  dir-steering/out/v41-fusedmsuiche-abl-ortho.f32 --residual2 5 --target2 <tau2>`
  where `tau2` is calibrated like 4.4 along `abl_perp`. Verify: measurements
  block with the tables, the D6 verdicts (overshoot variant and floor claim
  separately), and the 2x2 Gram-form decision ("not needed" unless the floor
  claim is supported with a non-orthogonal pair).
- [ ] 6.7 Non-adoption. If both D6 rules end rejected or inconclusive, revert the
  edits of 6.1-6.5 (engine, frontends, kernel parameter, tests, docs, run.py),
  keeping 6.6's block. Verify: `grep -rn 'dir-steering-target\|residual_tau' --include='*.c' --include='*.h' --include='*.m' --include='*.metal' --include='*.md' --include='*.py' . | grep -v docs/steering-measurements.md | grep -v openspec/` prints nothing; `make test` green.

## 7. Arm 1: conditional gate (D5; only if G2 proceeded)

- [ ] 7.1 Options and plumbing. `ds4.h`: `const char *directional_steering_gate_file;
  float directional_steering_gate_tau;`. CLI and server: `--dir-steering-gate-file`
  and `--dir-steering-gate-tau` (range -2..2) next to the `-2` flags, help text
  "per-row cosine gate: at or above tau the second slot applies alone, below it
  the first". Engine struct: `float *directional_steering_gate_dirs; float
  directional_steering_gate_tau;`. `cpu_load_directional_steering`: when a gate
  file is given, require both `residual_scale` and `residual2_scale` nonzero
  (error `ds4: --dir-steering-gate-file needs --dir-steering-residual and
  --dir-steering-residual-2`), load it with `ds41_load_steering_matrix`
  (validation reused), and build `gate_tau_per_layer[40]`: `tau` where the gate
  row is nonzero, `+2.0f` where it is zero (a zero row selects slot 1). Graph:
  `ds4_gpu_tensor *gate_dirs; ds4_gpu_tensor *gate_tau_rows;` uploaded at session
  create next to `residual_dirs2` (~31920), freed next to it (~23210). Add
  `DS4_ENV(DS4_V41_STEERING_GATE_TRACE, probe, unset, "409: print per layer the
  rows the steering gate sent to the second slot (gate L=<il> rows=<n> fired=<k>);
  diagnostic, output unchanged")` to `ds4_env.def`. Verify: build clean; `make
  env-check` passes; `--help | grep -c dir-steering-gate` prints 2 for CLI and server.
- [ ] 7.2 Kernel and references. New kernel
  `kernel_dsv4_directional_steering_gated_project_f32` in `metal/dsv4_misc.metal`
  after the existing one, args `{width, rows, layer, n_threads, scale1, scale2,
  tau1, tau2}` plus buffers `x, dirs1, dirs2, gate_dirs, gate_tau_rows` and a
  threadgroup scratch of `4*n_threads` floats: one pass accumulating `wh, hh,
  d1h, d2h`, four reductions, `fire = hh > 0 && wh >= gate_tau_rows[layer] *
  sqrt(hh)`, then `coeff = fire ? scale2*(d2h - tau2*sqrt(hh)) : scale1*(d1h -
  tau1*sqrt(hh))` (targets from group 6 if it survived, else pass 0 and use the
  plain products) and `x -= coeff * (fire ? d2 : d1)`. When `fire`, write 1 to a
  per-row `fired` byte buffer the host reads only under the trace env. Host
  wrapper `ds4_gpu_directional_steering_gated_project_tensor` in `ds4_metal.m`
  modelled on the existing wrapper (~29758), pipeline fetched by name. `ds4.c`:
  `cpu_directional_steering_gated_project_rows` (same semantics, double
  accumulation like the existing CPU fold), `ds41_steering_gate_active(g)`
  (gate tensor present and both slots active and not the disable env), and
  `ds41_steer_attention_input_gated(g, x, il, rows)` which increments
  `ds41_steered_rows_total` by `rows`, dispatches the gated kernel, and under
  `DS4_V41_STEERING_GATE_TRACE` reads the fired bytes and prints the trace line.
  At the three routes (`ds41_hc_mix` ~23678-23679, `ds41_hc_mix_batch`
  ~24048-24049, and the suffix path that reaches them) call the gated helper
  instead of the two sequential helpers when `ds41_steering_gate_active(g)`;
  leave the ungated code textually unchanged. Verify: build clean; `make test`
  green with the existing fold output unchanged.
- [ ] 7.3 Tests. `check_steering_fold`: random gate rows and `tau` chosen so
  about half the batch rows fire; Metal gated kernel vs the CPU gated reference
  within the existing tolerance on decode and batch shapes; REQUIRE that with
  `tau = 2` the result equals the slot-1-only fold exactly and with `tau = -2`
  the slot-2-only fold exactly (same inputs, same kernel path as the ungated
  helper, so bitwise). `check_steering_file`: gate file with one slot off is
  refused; a zero gate row yields `+2` in `gate_tau_per_layer`.
  `check_steering_admission`: two model-backed configurations, gate `tau 2`
  bitwise equal to slot 1 alone, gate `tau -2` bitwise equal to slot 2 alone.
  `make test-deepseek41-decode-switch SWITCH=DS4_V41_STEERING_GATE_TRACE` exact
  (the trace changes no output). Verify: `./tests/test_deepseek41_graph
  --steering-fold` prints a gated-cases line; admission and decode-switch PASS
  (user-run).
- [ ] 7.4 Docs. `dir-steering/README.md`: a "Gated rank-2" paragraph after the
  Rank-2 one (semantics, cosine units, zero gate row, the two identities, the
  trace env); flag table rows. `AGENTS.md` Identity row clause and the trace env
  in the `DS4_*` paragraph if one lists probes. Verify: `grep -n 'gate' dir-steering/README.md AGENTS.md ds4_env.def`.
- [ ] 7.5 Add `--gate FILE --gate-tau T` to `eval/run.py` like 6.5 (`--gate` needs
  `--steer` and `--steer2`). Verify: `python3 eval/run.py --self-check`.
- [ ] 7.6 **User-run.** Gated arm: `--steer dir-steering/vectors/v41-msuiche.f32
  --residual 5 --steer2 dir-steering/vectors/v41-abliteration-attn.f32 --residual2 6
  --gate dir-steering/out/v41-floor-resist.f32 --gate-tau <tau from 4.3>` on the
  floor plus the 32-hard set (`--max-tokens 2048 --judge base`), and `--suite
  benign-smoke` with `DS4_V41_STEERING_GATE_TRACE=1` in the server environment to
  record the benign fired fraction per layer; forced-prefix KL against the
  `msuiche@5` arm per the 403 benign-fidelity procedure (`eval/score_kl.py`).
  Verify: measurements block with the floor table, the hard-set count against
  29/32, benign task pass and KL against `msuiche@5`, the fired fractions, and the
  D5 verdict.
- [ ] 7.7 Non-adoption. If the D5 rule ends rejected or inconclusive, revert
  7.1-7.5 (engine, kernel, wrapper, tests, env line, docs, run.py), keeping
  7.6's block. Verify: `grep -rn 'gate' ds4.c ds4.h ds4_cli.c ds4_server.c
  ds4_metal.m metal/dsv4_misc.metal ds4_env.def | grep -i steer` prints nothing;
  `make test` and `make env-check` green.

## 8. Arm 5: residual-write projection site (D8)

- [ ] 8.1 Route inventory before code: list in a comment block at the top of the
  new helper (8.2) every write of the attention output and of the MoE output into
  the HC streams, with function names: decode `ds41_attention_expand` (~23721,
  fused `ds4_gpu_dsv41_matmul_expand_rows` or `ds41_attention_b` +
  `ds4_gpu_hc_expand_split_bf16_tensor`), decode MoE `ds41_graph_after_moe`
  (~24314, fused expand or `ds41_shared_down` + `..._expand_split_add_bf16_tensor`,
  and the `tp_world == 2` branch), batch `ds41_graph_after_attention` (~23986)
  and the MoE write inside `ds41_moe_batch` (~24370), and the decoder-suffix path.
  Verify: for each, a grep by name finds exactly the listed call, and the block
  states which fused kernel a steered layer must skip.
- [ ] 8.2 Options and plumbing. `ds4.h`: `const char *directional_steering_write_file;
  float directional_steering_write;`. CLI and server flags
  `--dir-steering-write-file`, `--dir-steering-write` (range -100..100, default 0),
  help "projects the attention and MoE outputs of layers 1-39 along the file's
  rows before they enter the residual streams; 1 = projection". Engine fields,
  option copy, load and validation in `cpu_load_directional_steering` (file
  required when the scale is nonzero; `ds41_load_steering_matrix`), open line
  `ds4: V4.1 residual-write steering: %s at v41_residual_write rev 1, scale %g`.
  Graph fields `write_dirs`, `write_scale`; upload and free next to the fold's.
  Persistence: extend the "nonzero steering scale" predicates (~28822-28830, the
  KV-disk skip in the server, the snapshot refusal) to include the write scale.
  Verify: build clean; `--help | grep -c dir-steering-write` prints 2 for both
  frontends; a run with `--dir-steering-write 1` and no file fails with the
  "needs --dir-steering-write-file" error.
- [ ] 8.3 Apply. `ds4.c`: `ds41_write_steering_active(g)`, `ds41_steer_write(g, x,
  il, rows)` calling `ds4_gpu_directional_steering_project_tensor(x, g->write_dirs,
  il, DS4_N_EMBD, rows, g->write_scale, 0.0f)` and counting
  `ds41_write_steered_rows_total`. At each site from 8.1, when active: take the
  unfused path (`ds41_attention_b` into `g->block`, then project `g->block`; MoE:
  `ds41_shared_down`, then project `g->routed` and `g->shared` separately, which
  equals projecting their sum), then the existing expand kernel; `tp_world == 2`:
  project `g->block` before its expand; batch: the same around
  `ds41_graph_after_attention` and the `ds41_moe_batch` write. Off: textually
  unchanged paths. Verify: build clean; `make test` green.
- [ ] 8.4 Tests. New `check_steering_write_routes` in `tests/test_deepseek41_graph.c`
  modelled on `check_steering_routes` (~2945): with a unit direction at write
  scale 1, decode vs batch vs reconstructed rows agree within the fold test's
  tolerance, `ds41_write_steered_rows_total` counts every route's rows, and a
  readback of `g->block` and of `routed + shared` after the projection has
  `|dot(r, out)| / |out| < 1e-3` on a sampled layer. Dispatch `--steering-write-routes`
  in `main` next to `--steering-routes` (~3110) and add Makefile target
  `test-deepseek41-steering-write-routes` with a `make help` line (~49-50).
  `check_steering_admission`: write file present with write scale 0 is bitwise
  the unsteered run; write scale 1 with the fold off refuses snapshots like the
  fold does. Verify: `make test-deepseek41-steering-write-routes` and
  `make test-deepseek41-steering-admission` PASS (user-run).
- [ ] 8.5 Docs and cost. `dir-steering/README.md`: a "Residual-write site" section
  (site name, revision, what is projected, why the abliteration vector belongs
  here, the persistence guards), flag table rows; `AGENTS.md` Identity row
  clause; `docs/steering-measurements.md` cost block measured as the README
  "Cost" paragraph did (ABAB x4, 2K prompt, 256 tokens, fixed
  `--ssd-streaming-cache-experts 82GB`, one CLI process per run): off, write only,
  write + fold. Verify: the block has the three medians and the percent.
- [ ] 8.6 Add `--write-file F --write W` to `eval/run.py` like 6.5. Verify:
  `python3 eval/run.py --self-check`.
- [ ] 8.7 **User-run.** Two axis-A arms on the floor plus the 32-hard set:
  `--write-file dir-steering/vectors/v41-abliteration-attn.f32 --write 1` alone,
  and the same with `--steer dir-steering/vectors/v41-msuiche.f32 --residual 5`;
  `--suite benign-smoke` for the second with the KL procedure of 7.6. Verify:
  measurements block with tables, counts against 29/32, benign guard, the cost
  from 8.5, and the D8 verdict.
- [ ] 8.8 Non-adoption. If the D8 rule ends rejected or inconclusive, revert
  8.2-8.6 keeping 8.7's and 8.5's blocks. Verify: `grep -rn 'residual_write\|dir-steering-write\|write_dirs' --include='*.c' --include='*.h' --include='*.m' --include='*.md' --include='*.py' --include='Makefile' . | grep -v docs/steering-measurements.md | grep -v openspec/` prints nothing; `make test` green.

## 9. Integration and handoff

- [ ] 9.1 Consolidated results: one dated block at the top of
  `docs/steering-measurements.md` with a table of every arm (id, configuration,
  vector sha256s, scales, run ids, floor 6/372/426, hard-set count, benign guard,
  verdict), the gate verdicts, and the production recommendation (unchanged
  `msuiche@5` / `fused@7` unless an arm is supported, in which case the supported
  configuration and its exact flags). Verify: the block links each arm to its own
  earlier block by date and run id.
- [ ] 9.2 Vectors: any direction a supported arm uses that lives in
  `dir-steering/out/` is copied to `dir-steering/vectors/` with sidecar and a row
  plus sha256 in `dir-steering/vectors/README.md`; rejected candidates stay in
  `out/`. Verify: `shasum -a 256 dir-steering/vectors/*.f32` matches the README.
- [ ] 9.3 Model-less gate: `make test` exits 0 **and** prints every test's name
  including the new self-checks (compose_geometry, mask_layers, capture_fold,
  analyze_fold, derive_native_direction) and the steering fold and file tests;
  `make env-check` passes; `grep -c '^test:' Makefile` prints 1. Verify: paste the
  test-name lines into the 9.1 block.
- [ ] 9.4 Model-backed gate (**user-run**): `make test-deepseek41-steering-admission`,
  `make test-deepseek41-steering-routes`, and for each surviving new `DS4_*` name
  `make test-deepseek41-decode-switch SWITCH=<name>`; the write-routes target if
  arm 5 survived. Verify: PASS lines recorded in 9.1.
- [ ] 9.5 Parity of the unsteered path from the StarForge checkout:
  `SF_PARITY_FLAGS=--ssd-streaming tools/parity-check.sh sf-ds4-1flash`, ten
  token-identical prompts, no speed trip. Verify: output directory and upstream
  SHA recorded in 9.1; hand the tree to `420`.
- [ ] 9.6 No-flag audit: `./sf-ds4-1flash --help | grep dir-steering` lists only
  the flags of supported arms plus the pre-existing ones; `ds4_env.def` has no
  `409` line for a rejected arm; `openspec/changes/405-steering-investigations/tasks.md`
  still carries the ten "moved to 409" annotations. Verify: the three greps in the
  9.1 block.

## Workflow follow-up

- Archive this change after `420` has run on the tree where its last code landed
  (`openspec archive 409-floor-operator-family`), then sync the delta specs.
- If arm 3's rank-2 native projector beat rank-1 (5.3 "follow-up change needed"),
  open the next change for a slot array (rank 3-4) with its own pre-registration.
- If the open question on benign capture size was triggered, the second benign
  capture is a plain re-run of 3.2 with `--classes benign --benign-count 100`.
