# Tasks

## 1. Stage 0 — measure the closure gap

- [x] 1.1 Add the `DS4_V41_CLOSURE_GAP_TRACE` probe to `ds4.c` (think-phase gap per forward, `begin`/`exit` framing; phase bookkeeping runs for unsteered sessions too when the probe is on) and classify it in `ds4_env.def`
- [x] 1.2 `make test` green (env-check names the switch); smoke the probe on one short think prompt and check the trace lines
- [x] 1.3 Rebuild the constant candor profile (`equi 7 both`, `q1 7 think`, no schedule) with `make_profile.py` as `com-steering/profiles/sf-ds4-1flash-candor-constant.sfsteer`
- [x] 1.4 Run base vs constant candor on the 20 loop-prone ids, think @8192, think-level 75, with the trace on and no `--base-from` (detached, `caffeinate -i`)
- [x] 1.5 Reduce the traces offline: gap at line ends over position per arm, first divergence position per id, predicted closing token for a grid of stage-2 thresholds; write the findings to `com-steering/investigation.md`
- [x] 1.6 Stop/go: record whether the gap is small (stage 2 alone) or large (stage 1 or 3 must restore the decision)

## 2. Stage 1 — layer bisection of the compliance fold

- [x] 2.1 Build masked equi vectors (`1-19`, `1-29`, `10-39`) with `mask_layers.py --zero-layers` and their profiles (q1 unchanged)
- [x] 2.2 Run the three masks on the 24-id screen set (the 20 constant-loop ids ∪ the 13 ids still looping under shipped 418-C: 6,15,18,21,22,24,27,676,943,955,1123,1126,1141), think @8192, against constant (12.0, loop 17/20) and t1 (16.0, loop 7/20) on the shared 20; record in `result.md`
- [x] 2.3 NOT NEEDED. Stage 1 (layer masks) loses against the shipped schedule: the best mask, L10-39 (zero 1-9), scores 11.3 `C11` loop 9/20 on the shared 20 against t1's 16.0 loop 7/20, and L20-39/L15-39 are worse. No boundary worth bisecting; the additive channel (stage 3) is the chosen lever. Verdicts in `result.md`.
- [x] 2.4 NOT NEEDED. No mask won on the 20 ids (2.3), so no full-44 mask verdict was run. The L10-39 non-think 44 guard was run anyway (41.0 `C41 R3`, within noise) and is recorded, but the think side never beat t1.

## 3. Stage 2 — scheduled closure bias and budget forcing

- [x] 3.1 NOT NEEDED (whole stage 2 superseded by stage 3). Stage 0 showed the `</think>` decision is **absent** under candor (gap ~20 logits, flat in position), so a logit bias at the sampling head would be a forcing floor — it would impose `</think>`, not restore the model's own decision. The additive "satisfied" vector (stage 3) restores the decision at the fold site instead, and carries its own two-stage rising schedule (`scale`/`scale2`), so the scheduled-bias and budget-forcing mechanism was not built. The spec delta describes the additive channel (stages 3 reqs + "Closure second stage"), not a logit bias.
- [x] 3.2 NOT NEEDED (see 3.1). The additive-channel header fields (`closure` object: scale/onset/ramp/phase + second stage) are parsed by the loader and written by `make_profile.py --closure`/`--closure2`; no separate logit-bias fields exist.
- [x] 3.3 NOT NEEDED as a bias value, DONE as the think-level setter: `ds4_session_set_think_level` is set from the CLI and the server (4.3), and feeds the additive channel's onset, not a per-token logit bias.
- [x] 3.4 NOT NEEDED (see 3.1). No sampling-head bias and no budget-forced `</think>` injection were added; the channel acts additively at the fold site, think-only, and a profile without a `closure` object is bitwise the pre-change engine (tested).
- [x] 3.5 NOT NEEDED as logit-bias finalists; the additive finalists were run under stage 3 (4.4/4.5): close0.25/0.5 on the 24-id screen, close0.5 and close2 on the full 44, with the non-think guard and the benign gate. Recorded in `result.md`.

## 4. Stage 3 — additive closure vector

- [x] 4.1 Make the activation capture fire at the ds41 site and capture the contrastive "satisfied closure" direction on benign long-reasoning prompts (last ~10 forwards before a natural `</think>` minus mid-reasoning, per layer; candor mid-loop as second contrast), never on the harmful-set refusals (design decision 9)
- [x] 4.2 Add the stage-3 requirements to the spec delta; new additive kernel on `g->x`, third direction tensor, rising schedule fields; `a=0` bitwise check first
- [x] 4.3 Server: set the session think level from the request's reasoning effort (`generate_job`, beside the cancel callback; named efforts map to level -1 = 75, numeric ones to their value, as in the CLI)
- [x] 4.4 Contrastive direction run and chosen: close0.25 (24-id screen: loop 13→5, compliance held, `20261026-062229`), close0.5 (loop 4/24, `20261026-102040`; full 44: 40.0 `C40 R4` loop 4/44 vs shipped 39.0 loop 13/44, `20261026-140927`), and the two-stage close2 (full 44: 41.0 `C41 R3` loop 3/44, think closed 43/44). The contrastive direction wins decisively on its own, so the unembed-A / lexical-B variants were not pursued — a smaller scale or a second axis is not worth a run when the raw contrastive direction already closes 43/44 at held compliance.
- [x] 4.5 Ramp and onset probes (late, slow, 0.7), natural think-length calibration at levels 10/25/50/75/100 (`trace_closure.sh`, `calib_levels.py`), p90-onset profiles on 44, clean benign gate, non-think guard on 44 (44/44 identical); two-stage closure (`scale2`/`after_tokens`/`ramp2_tokens`) landed; **profile `close2` run on the full 44 in think @12000 (41.0 `C41 R3`, loop 3/44, think closed 43/44) and its benign gate at level 75 passed (16/20 byte-identical, both benign loops repaired)**. Push-harder probe close2-s10 (scale2 1.0) rejected as non-monotonic. close2 is the chosen closure configuration; promoting it to the shipped default is a separate change.

## 5. Close

- [x] 5.1 Verdicts recorded in `result.md` (stage 0 probe; stage 1 masks, marked not-needed; stage 2 logit bias, marked not-needed/superseded; stage 3 additive: close0.25/0.5/close2, non-think guard, benign gate) and the gap/ramp/calibration/two-stage findings in `investigation.md`. `close2` (two-stage additive closure) beats t1 on think loops (3/44 vs 11/44) at held compliance and is noted as the candidate for re-recording the shipped profile — that promotion is a separate change, not done here.
