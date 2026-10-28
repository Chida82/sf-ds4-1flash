# Tasks

## 1. Remove the engine probes
- [x] 1.1 Closed-loop controller: session fields, graph readback tensor, env parsing, per-token step
- [x] 1.2 Decay and cyclic schedules: engine and session fields, the five CLI/server flags, `DS4_STEERING_SCHEDULE_DEBUG`
- [x] 1.3 Probe-dosed second slot: `--dir-steering-probe-2`, the probe matrices and the non-unit-row loader path
- [x] 1.4 Fold activation capture: `DS4_V41_DUMP_STEER_INPUT` and its three call sites
- [x] 1.5 Phase ablation `DS4_STEERING_PHASE`; CLI `--perplexity-dump`
- [x] 1.6 Drop the seven names from `ds4_env.def`; `make env-check` passes

## 2. Return the Metal side to upstream
- [x] 2.1 Revert the kernel's probe and readback arguments in `metal/dsv4_misc.metal`
- [x] 2.2 Revert `ds4_gpu_directional_steering_project_tensor` to upstream's signature; drop the `_rb` variant
- [x] 2.3 Confirm `ds4_metal.m`, `metal/dsv4_misc.metal` and `ds4_gpu.h` are byte-identical to `main`

## 3. Reduce the harness
- [x] 3.1 Keep the ten modules `run.py` imports; remove the rest and the stored arms
- [x] 3.2 Strip the removed flags from `common.build_cli`, `generate.gen`, `run.py` and the manifest identity
- [x] 3.3 Repoint `make eval-refusal-selfcheck` at the modules that remain
- [x] 3.4 Move the measured vectors and the profile to `com-steering/`

## 4. Remove the steering tests
- [x] 4.1 Revert the steering additions to `tests/test_deepseek41_graph.c`; the file matches `main`
- [x] 4.2 Remove `tests/test_steering_admission.py` and the three model-backed `make` targets
- [x] 4.3 Remove the three steering lines from `make test` and the three help lines
- [x] 4.4 Check the Makefile tail survived the edit (`test:`, `clean:` and the other rules still exist)

## 5. Verify
- [x] 5.1 `make test` passes
- [x] 5.2 Unsteered generation byte-identical to `main` on the parity prompts and one reasoning prompt
- [x] 5.3 Steered generation byte-identical to the pre-prune binary, reasoning and non-reasoning
- [x] 5.4 Correct the two stale requirements in the landed spec
