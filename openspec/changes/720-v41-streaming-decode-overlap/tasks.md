# Tasks

## 1. Registry

- [ ] 1.1 `docs/upstream-prs.md`: split the five-commit `history: resident` row; `be2773b` covered by `30`, `57df7a5` unreachable (batches refused under streaming), `565db43` dropped (reads, not rows), `f0b4f55` and `26335c7` -> `720`

## 2. Stage 0: pre-screen

- [ ] 2.1 `f0b4f55`: compare the fused index-query RoPE + FP4 quantize with the separate steps on random inputs including exact midpoints; stop the candidate if any element differs
- [ ] 2.2 `f0b4f55`: micro-bench the per-layer RoPE work the table removes (8 index-source layers + the attention RoPE sites) against the table build
- [ ] 2.3 `26335c7`: micro-bench the HC weight dispatches that would leave the critical path; check `g->x` / `g->flat_norm` use in the split-deferred miss stage
- [ ] 2.4 Record each figure in `speed-bench/perf-record.md`; candidates under 0.5% of a decode token stop with a rejected-ideas row

Stage 0 so far (2026-11-05 night, encoder timeline of a 51-token decode run on
the `700` tree, `82GB`; pass boundaries serialize, so these are upper bounds):
every `kernel_dsv41_rope` and `kernel_dsv41_rope_quantize` together take
1.36 ms of GPU per token, the ceiling of what `f0b4f55`'s table could remove;
`kernel_dsv41_hc_block_input` takes 3.3 ms per token (two per layer), the
ceiling of what `26335c7` could take off the critical path by overlapping it.
Both ceilings pass the 0.25 ms gate, so the remaining stage-0 work is the real
share each commit removes (a per-kernel micro-bench) and the FP4 midpoint check
of 2.1.

## 3. Port (only candidates that pass)

- [ ] 3.1 Port under streaming with its switch (upstream's name where it exists), classified in `ds4_env.def`; kernel checks from the commit
- [ ] 3.2 `make test`, `make test-deepseek41-metal`, and `make test-deepseek41-decode-switch` per switch, also with a small cache so tokens miss
- [ ] 3.3 `ab_bench.py --kinds decode,cold-2500 --bitwise` against `main`; keep under the intake rule, else revert with a rejected-ideas row

## 4. Docs

- [ ] 4.1 `AGENTS.md` decode switch list for anything kept; registry rows final
