# Tasks

Outcome 2026-11-06: tasks 1.1-1.3, 2.1 and 2.3 were done in worktree
`p740-bf16-index` (on top of `690`): bitwise, and neutral at 40K / 72K. By 2.3
the change is not kept; the result is recorded with `690` (perf-record,
rejected ideas). 2.2 (restore past 8192 keys) was not run.

## 1. Port (on top of `690`)

- [x] 1.1 Port `kernel_dsv41_index_keys_bf16` and the bf16 scorer kernels into `metal/dsv4_misc.metal` byte for byte, and `ds4_gpu_dsv41_index_keys_bf16` / `ds4_gpu_dsv41_indexer_score_row` into `ds4_metal.m`, as `b3f5018` has them
- [x] 1.2 `ds4.c`: the per-owner bf16 views and flag in the graph, the store after every index-key producer (decode and prefill), the rebuild on restore, the decode call through `score_row`; `DS4_METAL_DISABLE_V41_INDEX_BF16` classified in `ds4_env.def`
- [x] 1.3 Port upstream's bf16-view kernel check; `make test` and `make test-deepseek41-metal` pass

## 2. Verify

- [x] 2.1 Bench logits at 40000 and 72000 (`--ctx-alloc 81920`, `60GB`) byte-identical to the `690` tree's, with and without the switch
- [x] 2.2 (not run: the change was dropped at 2.3) A session saved and restored past 8192 keys decodes the same tokens as an unbroken run
- [x] 2.3 Long-context bench ABBA against `690` (40000 then 72000, four runs each, as `690` measured); keep if decode gains and prefill does not lose

## 3. Docs

- [x] 3.1 (as a dropped change: `docs/upstream-prs.md` row and perf-record rejected ideas, landed with `690`; no AGENTS.md switch) `docs/upstream-prs.md` (`64ceeea` out of `history: long`), `AGENTS.md` (the switch with the long-context paragraph), `speed-bench/perf-record.md`
