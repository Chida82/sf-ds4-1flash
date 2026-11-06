# Tasks

## 1. Literal shapes (`b66c926`)

- [ ] 1.1 Port `kernel_mul_mv_q8_0_f32_bf16_pair_qa_kv` into `metal/dense.metal`, adapting the template arguments to the child's `kernel_mul_mv_q8_0_f32_rope_impl`
- [ ] 1.2 Port `kernel_mul_mv_q8_0_f32_bf16io_hc_expand4_static` into `metal/dsv4_hc.metal`
- [ ] 1.3 Dispatch both from `ds4_metal.m` under upstream's gates, with `DS4_METAL_DISABLE_V41_LITERAL_SHAPES`; classify it in `ds4_env.def`
- [ ] 1.4 Adapt upstream's `check_literal_shapes` into `tests/test_deepseek41_metal.c` (literal vs generic, bit-identical); `make test` and `make test-deepseek41-metal` pass
- [ ] 1.5 `make test-deepseek41-decode-switch SWITCH=DS4_METAL_DISABLE_V41_LITERAL_SHAPES` passes

## 2. Engram gate (`e99dc21`, conditional)

- [ ] 2.1 Port `kernel_dsv41_engram_add_tg256` and its kernel check; run the check on this machine
- [ ] 2.2 If bit-identical: dispatch under upstream's gate with `DS4_METAL_DISABLE_V41_SPLIT_REDUCE`, classify it, and pass its decode-switch test. If not: remove the kernel and record why in `docs/upstream-prs.md`

## 3. Measure and decide

- [ ] 3.1 `ab_bench.py --kinds decode,cold-2500,append --bitwise` against `main` with the `b3f5018` sync landed
- [ ] 3.2 Keep if no metric is below zero and decode gains; otherwise revert and add a rejected-ideas row in `speed-bench/perf-record.md`
- [ ] 3.3 Review the change against AGENT.md and the surrounding idiom

## 4. Docs

- [ ] 4.1 `AGENTS.md` decode switch list; `docs/upstream-prs.md` rows for the six commits (taken, moved to `690`, or dropped, with reasons); `speed-bench/perf-record.md` result

## 5. Is the prefill 5000 loss noise? (before landing)

The first A/B measured the 5000-token prefill of `append` at -8.8%
(-15.0..-1.4), wholly below zero. Neither switch moves it, and an A/A of two
identical builds (`730`) moved the same metric by -6.3% (-10.4..+5.0). That
reading is not yet proof; these steps decide it.

- [ ] 5.1 Reachability. Run an encoder timeline (`DS4_METAL_ENCODER_TIMELINE`) of the 5000-token prompt alone, prefill only, on the `700` tree. Count the dispatches of `pair_qa_kv`, `expand4_static` and `engram_add_tg256` inside the prefill sweep. Their gates (one row; Engram at most 16 rows) predict zero. If the count is not zero, the prefill runs `700`'s code: treat the loss as real and find out why.
- [ ] 5.2 GPU time. With `DS4_METAL_CB_TIMES=1`, sum the command-buffer GPU time of that prefill on the sync tree and on `700`: 5 runs each, alternated, cooled to 55 C before each. If the sums agree within 0.5%, the wall-clock gap comes from SSD reads and scheduling, not from compute.
- [ ] 5.3 Null distribution. In one session, alternate two `ab_bench.py --kinds append` runs: the sync tree against `700` (A/B), and the sync tree against a second build of itself (A/A'). Run A/B, A/A', A/B, A/A', at least 20 pairs each in total. Compare the per-pair prefill 5000 differences of A/B with those of A/A' (permutation test on the medians).
- [ ] 5.4 Decide. It is noise if 5.1 counts zero, 5.2 agrees and 5.3 cannot tell A/B from A/A' (p >= 0.05). Then record the figures in `perf-record.md`, and the intake rule is met. Otherwise the loss is real: look for its indirect cause (pipeline creation at init, library size, memory layout) before landing, and do not land until it is explained or removed.
