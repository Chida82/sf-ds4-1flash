# Design

## Context

- `320` has landed. The facts below come from its section and from `310`'s:
  - c(k) in the child;
  - the miss share of a verify cycle;
  - prose under back-off;
  - the memory timeline with the drafter beside `82GB`.
- **The automatic budget** is computed in `ds4_engine_configure_streaming_cache_budget` (86% of the recommended working set). It knows the context buffers and the prefill reserve, not the drafter.
- **`170`** closed route-prediction prefetch for decode: the guess costs about 0.3 ms per token, more than the third of the hideable miss time that the drives could sustain. Decode misses are read by the reader pool and split across both drives (`145`, `260`).
- **#1073's draft length** is `dspark_confident_prefix_len`: the first position whose own confidence falls under the threshold, with no cost term. `310` D7b replayed it against DeepInfer's expected-cost rule and measured the confidence's calibration on this target. Both rules are described in `310`'s design.
- **#1168** (V4 Flash) doubles the pause on consecutive rejected proposals (2..64 cycles), leaves the first miss unpunished, and spends earned credit on isolated misses. #1073's `ds41_draft_adapt` instead compares smoothed tokens/s of drafting and plain cycles, and skips 4, 8, 16, then 32 cycles. Under streaming a rejected verify costs more than resident, so the two are compared on the harness, not by reading.

## Goals / Non-Goals

**Goals:**
- Memory that is honest with the drafter loaded.
- A verify cycle's misses read no slower than one decode token's, per expert.
- Defaults chosen on the owner's content.

**Non-Goals:**
- A new drafter architecture. A Markov or other head beyond #1073's is not part of this.
- Server behavior (`340`).
- Changing the `82GB` measurement configuration.

## Decisions

### D1. Order by measured share
The steps run in the order of what `320` left on the table:
- the miss share of a verify cycle → S2;
- prose under the rule → S3 first;
- memory pressure → S5.

S1 always runs: it fixes a budget that over-commits.

When prose is under the rule and `310` D7b's replay favours the expected-cost rule, S4 runs before S3. The rule turns cycles that would lose into plain steps with no verify, so prose may already pass; S3 is then judged on top of it, where it only has to save the drafter's time.

### D4. S4: the expected-cost rule for one request
- **The rule.** After `ds41_draft_propose`, with `P_j = prod_{i<=j} sigmoid(conf_i / T_i)`:
  - `k* = argmax_{k in 0..K} (1 + sum_{j<=k} P_j) / t(k)`;
  - K is the block size, also bounded by EOS and the context exactly as today;
  - ties go to the smaller k.

  The drafter's own time is spent before the choice, so it is not in t(k).
- **Cost model.**
  - **Seed.** `t(k) = t_plain * r(k)`, where `r(k)` is `t_cycle(k) / t_decode` from `310`'s `speed-bench/dspark-verify-curve.json`, interpolated between its frontiers by context position. The ratios are compiled in as a small table, and `t_plain` is the plain token time that `ds41_draft_adapt` already tracks.
  - **Runtime correction,** as in DeepInfer's `ForwardRuntimeEstimator`: a windowed median of `(t_measured(k) - t(k)) / (k + 1)` over the last cycles, shared by all k and clamped at zero below. A k that is rarely chosen still gets a current price.
  - **Why medians.** A cycle that hits a run of expert misses is an outlier. A mean would make the next cycles draft too little, and a median does not. Window lengths come from DeepInfer (9 samples for the sampler term, a long window for the residual) and are checked in S4 rather than assumed.
- **Calibration.** If `310` found the confidence miscalibrated, the per-position temperatures `T_i` it fitted are compiled in, as DeepInfer's `DEEPINFER_DFLASH_CONFIDENCE_HEAD_TEMPERATURE` does. Otherwise `T_i = 1`.
- **Output.** k never changes which tokens greedy decoding keeps. Verification is exact and `320`'s rows are bitwise at every k, so the token gate must pass unchanged. Timing makes k, and therefore the counters, differ run to run. `DS4_DSPARK_COST_FROZEN=1` (a `test` switch in `ds4_env.def`) turns off the runtime correction, so a run's choices depend only on the seed and the confidences.
- **Back-off.** `ds41_draft_adapt` and S3's schedule stay: k* = 0 still pays for the proposal. Their input does not change.
- **Switch.** `DS4_DSPARK_DISABLE_COST_RULE=1` (`disable`) restores the threshold rule with its default threshold. It is the harness's A arm for S4 and must be bitwise to the previous step.
- **Rejected alternative.** A per-k table of measured times with no shared term. With one request, k = 4 or 5 may run rarely and its entry would go stale. DeepInfer's shared slope keeps every price current.

### D2. S1 is judged on memory, not speed
- **Rule.** A budget that ignores the drafter can push static weights and the file cache out. The step's check is `310`'s timeline under the automatic budget: zero swapouts and at least 18 GiB available.
- **Measurement.** The harness A/B then runs under the explicit `82GB` flag, which this step leaves unchanged: bitwise, nothing below zero.

### D3. S5 only on evidence
A smaller drafter costs acceptance, because the drafter's errors become rejected rows. It is built only if both hold:
- the replay of `310` D5 shows that the slots the drafter takes cost more decode than the measured acceptance gap between MXFP4 and a Q2 drafter would give back;
- the owner agrees to publish the file.

## Risks / Trade-offs

- **[S2 adds reader contention with no gain]** → The step is kept only if the miss time of a cycle falls, measured with `--cache-stats`, and by the keep rule.
- **[S4 overfits the two harness texts]** → The defaults are checked once on the chat and tool kinds of `310`, and a cap that loses there is not chosen.
- **[The expected-cost rule chases timing noise]** → Medians and the frozen switch. If two runs with the switch off disagree beyond the harness's resolution while frozen runs agree, the correction's window is lengthened before the step is judged.
- **[The confidence is calibrated for a different target precision]** → `310`'s calibration table decides `T_i`. If no temperature calibrates it, S4 keeps the threshold rule and records why.
