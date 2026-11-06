# Tasks

## 1. Default and switch

- [ ] 1.1 `ds4_gpu_model_resource_options`: untracked unless `DS4_METAL_MODEL_TRACKED` is set; remove the `DS4_METAL_MODEL_UNTRACKED` read
- [ ] 1.2 Add `ds4_gpu_tensor_alloc_weights` (declared in `ds4_gpu.h`) with the same options; allocate the narrow copies through it
- [ ] 1.3 `ds4_env.def`: add `DS4_METAL_MODEL_TRACKED` (`disable`, `unset`), remove `DS4_METAL_MODEL_UNTRACKED`; `make test` passes (env-check included)
- [ ] 1.4 Check that no kernel takes a model view or a narrow copy as an output, and that the copies are filled before their first command buffer

## 2. Verify

- [ ] 2.1 Two processes, same prompt and frontiers (bench `--dump-frontier-logits-dir`, 2048 and 8192), with and without `DS4_METAL_MODEL_TRACKED=1`: every dump byte-identical
- [ ] 2.2 `make test-deepseek41-metal` passes
- [ ] 2.3 `ab_bench.py --kinds all --bitwise --b-env DS4_METAL_MODEL_TRACKED=1` on this tree; keep the default unless tracking wins a metric

## 3. Docs

- [ ] 3.1 `AGENTS.md` (narrow copies paragraph: untracked, the switch), `docs/upstream-prs.md` (`890898c`/`9fe88cd` row, `55b1e75` note), `speed-bench/perf-record.md` result
