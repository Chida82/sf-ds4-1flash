# Tasks

Start only after `865` has run. If its analysis A verdict is "go", start. With
any other verdict, ask the owner first: a failed 512-value probe is
inconclusive, and stage 0a alone (ten minutes) may still be worth running.

Edits `ds4.c`: follow the design edit by edit and stop at anything it does
not list.

## 0. Probe

- [ ] 0.1 The `exit_layer` block and edits 1-4 in `ds41_graph_step`; `ds4_env.def` line. `make test` passes and its output names `env-check`.
- [ ] 0.2 Bitwise guard with the variable unset: `make test-deepseek41-metal`, `make test-sysone`, `ab_bench.py --kinds decode --bitwise` against the previous commit.

## 0a. Timing gate

- [ ] 0a.1 Four server processes (L = 40, 28, 20, 12), warm-up plus five 250-token prompts each; median ms per prefilled token.
- [ ] 0a.2 Record the four medians and the two ratios in `sysone-bench/record.md`; apply the gate. On "stop": do task 2.2 and finish.

## 0b. Raw readout

- [ ] 0b.1 Nine server runs with the restrictions; `run.py` on the 300 items each, `sf.debug` on; keep the nine results files.
- [ ] 0b.2 Per-L table with state-level bootstrap intervals; apply the gate.
- [ ] 0b.3 `lens_fit.py --contrast`: the layer-contrast table from the nine files.

## 1. Stage 1 (only by the gate)

- [ ] 1.1 The capture in `ds41_graph_logits`; `ds4_env.def`; `make test`; with the variable unset, the 0.2 guard again.
- [ ] 1.2 Capture runs for the two candidate L; join by the last record per request (largest `pos`); assert the record count is twice the item count.
- [ ] 1.3 `sysone-bench/lens_fit.py` with the three translators; unit tests in `tests/test_sysone_bench.py`: bias and temperature recovered from synthetic logits; centroids classify three synthetic Gaussian classes; the leave-one-out temperature is finite.
- [ ] 1.4 Held-out tables by state and by schema; apply the gate.

## 2. Deliverable

- [ ] 2.1 `docs/system-one.md`, "Early exit": tables and the recommendation.
- [ ] 2.2 On "stop": revert the `ds4.c` and `ds4_env.def` edits; `git diff main -- ds4.c ds4_env.def` prints nothing; `make test` passes.
- [ ] 2.3 On "follow up": keep the probe, add the follow-up list to the docs, ask the owner before opening the next change.
