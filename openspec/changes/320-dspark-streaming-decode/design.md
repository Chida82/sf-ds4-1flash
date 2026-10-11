# Design

## Context

- **`310` has passed** (its perf-record section). It fixed:
  - the drafter file;
  - the default cap and confidence;
  - the kernel configuration whose verify rows are bitwise to one-row decode;
  - the prose rule for the opt-in flag;
  - the measured c(k).

  This design does not restate them. It names them as "`310`'s".
- **#1073 at `cad7933`** holds the drafter (`ds41_draft_*`), the cycle (`ds41_session_spec`, reached through `ds4_session_eval_speculative*`) and the back-off (`ds41_draft_adapt`).
  - It shares the support-GGUF loader (`ds4_dspark_weights`, `dspark_weights_validate_metadata`) with V4 Flash.
  - Its cycle already has an exact-sampling branch (`exact = rng && temperature > 0`).
  - When `ds41_draft_init` refuses, the session prints "DSpark drafting unavailable for this V4.1 session" and decodes normally.
- **This child deleted all of it**, as `AGENTS.md` "Speculative decoding: none" lists:
  - the flags and the `ds4_engine_options` fields;
  - the support-GGUF loader;
  - the V4 Flash DSpark capture;
  - the speculative API;
  - the TP spec cycles and VERIFY frames.
- **Main has the pieces verify rows need:**
  - `ds41_graph_step_batch`;
  - the expert cache with its selected-address table;
  - the decode miss path with overlap (`50`), keep-alive (`220`) and the selected-id mailbox (`210`).

## Goals / Non-Goals

**Goals:**
- A greedy single request runs faster under `--ssd-streaming --dspark` on code by at least `310`'s projection, with identical tokens.
- Without the flag, nothing changes, bitwise.

**Non-Goals:**
- The server, exact sampling and tool boundaries (`340`).
- The cache budget, a smaller drafter, union prefetch and tuning (`330`).
- An n-gram drafter (`350`).
- TP or pipeline drafting: refused, and `history: two-macs`.
- The V4 Flash DSpark engine, legacy MTP, `--dspark-strict` and `--quality`'s drafting role.
- Resident weights.

## Decisions

### D1. Port by call site from #1073, V4.1 only
- **What comes in.**
  - The nine DSpark commits, plus the parts of the shared loader and the speculative API that V4.1 reaches.
  - The public entry points keep upstream's names (`ds4_session_eval_speculative*`), but only their V4.1 branch exists.
- **What stays out.** Code that only V4 Flash, TP (`c674b19`), CUDA or ROCm reaches.
- **Why.** One PR owns the zone. Following it as written keeps the sync cheap if it merges.
- **Rejected alternative.** A rewrite smaller than the PR would make the zone this child's own at the first upstream merge.

### D2. Identical output by construction
Verify rows run only on kernels whose rows are bitwise to one-row decode: `310`'s configuration.
- That means the rows > 1 forms of the decode kernels, which `70` left out (`8be1005`, the `_rows` forms of `d8d1523`).
- The MMA rows (`262b4a6`, `a6b50ff`) stay `drop: output`.

Three tests hold it:
1. **Rows.** k+1 verify rows against k+1 one-row decode steps: logits and the KV rows written, bitwise. This is model-backed and lives in `make test` next to `test-deepseek41-decode-switch`.
2. **Rollback.** A cycle with a forced rejection at draft j must give the same next-token logits as a run that decoded only the accepted prefix, bitwise. This covers the open compression pair, the rings and the windows.
3. **Harness.** The token gate, A plain against B `--dspark`, on every kind it runs.

With output identical, `--dspark` is a speed option, not a semantic variant. That is what `AGENT.md` allows.

### D3. Verify rows under streaming: one union per layer
For each layer, the k+1 rows' routes are published once:
1. **Mailbox.** `210`'s mailbox is widened to (k+1) × 6 ids.
2. **Union.** The union of the experts is looked up in the cache.
3. **Misses** go through the decode miss path, overlapped with the rows' shared expert as in `50` and kept alive as in `220`.
4. **Multiply.** Each row's experts are multiplied through the selected-address table by the decode expert kernel in rows form.

The prefill's selected-addr kernels are used only if `310` found them bitwise to decode. The decode path is preferred because verify has at most six rows, and the decode path already overlaps their misses with work.

### D4. The drafter's memory
- **Loading.** The support GGUF is mmapped from the shared cache through the `gguf/` symlink (rule 9). Its tensors are made resident at load, like the static weights.
- **Budget.** The `82GB` flag stays the measurement configuration. The drafter is not taken from the cache in this change, and its resident size is printed at startup.
- **The automatic budget** (no flag) subtracts the drafter. That is `330`, after `310`'s memory evidence.

### D5. Flags under upstream's names
`--dspark`, `--mtp-model FILE` and `--dspark-confidence X` are added in the CLI and the bench, as in upstream, so its docs and examples hold.
- **Not needed:** `--dspark-strict`, because output is identical by D2.
- **Stay deleted:** `--mtp`, `--mtp-draft`, `--mtp-margin`, `--mtp-timing` and `--mtp-exact-sampling` (`340` decides the last one).
- **Statistics.** The bench prints the drafting counters per frontier (spec). The CLI keeps upstream's stats switch.

### D6. No drafting when sampling
- **The rule.** In this change, a temperature above zero turns drafting off with one notice.
- **Opportunistic sampling is not ported.** Upstream's default for sampled decoding accepts matching greedy drafts directly, which changes the sampling distribution. By the output rule that is `drop: output`.
- **Exact sampling** is already in the cycle and keeps the distribution. `340` enables and measures it.

### D7. Steps and how they are judged
- **S0, tool step.** The `decode-code` kind and the code text. It must give an A/A that is bitwise, with no metric below zero.
- **S1, the port.**
  - **Default path unchanged.** B without the flag against A = main: `--kinds decode,append --bitwise`, with nothing below zero. This proves capture and allocation are off without the flag.
  - **The gain.** B with the flag against A: target `decode-code` 2048 and 8192, which needs at least +1.5% because the port is above 800 runtime lines. `decode` (prose) follows `310`'s prose rule.
  - The port lands as one step. No part of it can be measured on its own, and the config forbids keeping a neutral step because a later one builds on it.
- **Reviews.** Then the config's two reviews, with any refinement measured like a step.
- **Parity and output.**
  - `tools/parity-check.sh` runs without the flag, because upstream refuses DSpark for V4.1 and cannot be an oracle for it.
  - D2's tests, plus greedy 1024 tokens with and without the flag on the parity prompts, are the oracle for the flag.

### D8. Registries before the flag ships
Rule 6 binds the child to StarForge's registry. The StarForge change (`AGENTS.md`, `README.md`, `tools/lib.sh`, the parity prompt file) is prepared in the same session and committed only on request, before or with the child's commit.

In the child:
- the section "Speculative decoding: none" becomes "Speculative decoding: DSpark (V4.1, opt-in)";
- the "Names that lie" table gets the reintroduced identifiers that carry V4 names;
- the DSpark commit lines of #1073 get `adopt -> 320`.

## Risks / Trade-offs

- **[A rows kernel is bitwise in `310`'s probe but not at some shape]** → The rows test runs k = 1..5 at both harness frontiers, and the harness gate runs on every kind.
- **[Upstream reshapes or drops #1073]** → The registry line records it. The zone then belongs to this child, and its size is the cost.
- **[The resident drafter pushes static weights out]** → `310`'s timeline is the evidence, and `330` owns the budget.
- **[Prose gets slower with the flag]** → Back-off is in S1. If prose still falls under `310`'s rule, `330`'s exponential back-off (#1168's idea) is its first step.
- **[Images in the context]** → The PR's routed shortcut is skipped for image rows. The rows test and one image prompt with the flag check tokens. If they differ, drafting turns off while the context holds image tokens, and that is noted in the spec.
