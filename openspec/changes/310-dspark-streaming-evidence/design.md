# Design

## Context

- **#1073's drafter** (head `cad7933`, `ds4.c`):
  - **Capture.** The target's residual stream, averaged over the HC copies, is captured at the target layers into a window of at most 128 rows (`DS41_DRAFT_WINDOW`). This happens during prefill and during every decode step. Prefill captures only the last window, so the first-token cost should be small.
  - **Rings.** `ds41_draft_pending` and `ds41_draft_commit` project the captured rows into one KV ring per stage.
  - **Proposal.** `ds41_draft_propose` runs three stages over a five-token block, and the confidence head scores each position.
  - **Verify.** `ds41_draft_verify` writes the rows' slots and runs `ds41_graph_step_batch` on k+1 rows of one session. Logits come per row from `ds41_output_projection_rows`.
  - **Rollback.** `ds41_draft_rollback` restores what the rejected rows changed: the frontier, the n-gram history, the window slots, the open compression pair and the rings.
  - **Draft length.** `ds41_session_spec` drafts `k = dspark_confident_prefix_len(conf, 5, threshold)`, capped by EOS and the context.
  - **Back-off.** `ds41_draft_adapt` keeps smoothed tokens/s of drafting and plain cycles (a = 0.25). When drafting falls under 0.9x plain for two cycles, it skips 4, 8, 16, then 32 cycles. `DS4_DSPARK_DISABLE_ADAPTIVE_DRAFTING` turns this off.
  - **The gate.** `ds41_draft_init` returns false when `g->streaming` is set.
- **What main already has.**
  - **`ds41_graph_step_batch`.** It serves the multi-session batch, which `ds41_sessions_batch_supported` excludes under streaming.
  - **A multi-row routed MoE through the expert cache:** `ds4_gpu_stream_prefill_batch_selected_addr_*`, automatic from 2 to 800 rows at 384 experts.
  - **`70`'s choice from #1073.** It took the one-row forms only. Its rows > 1 kernels, the MMA rows (`262b4a6`, `a6b50ff`, both `drop: output`) and the verify paths were left out.
- **This child's decode** (`perf-record.md`, `225` and README):
  - 29.6 tokens/s at 2048, about 34 ms per token, with `82GB`.
  - Misses are about 7% of a token. One miss is one expert of 9.5 MiB, read in a median 0.70 ms.
  - Hit rate 0.982 at 8078 slots, or 3.91 miss layers per token. The replay stops gaining at +770 slots.
- **The model used so far.**
  - The gain of a fixed draft length k is `(1 + a_1 + ... + a_k) / (1 + D + c k)`, where:
    - a_i is the probability that the first i drafted tokens are all accepted;
    - D is the drafter's cost per cycle (about 0.1);
    - c is the cost of one extra verify row, both in decode tokens.
  - The three acceptance profiles:
    - **code:** V4 Flash DSpark as reported upstream, 0.82..0.37;
    - **GSM8K:** V4.1 on GSM8K from vLLM issue #56797, 0.724..0.096, reported there as below the published reference;
    - **prose:** assumed, 0.45..0.01.

  | c | profile | k=1 | k=2 | k=3 | k=5 |
  |---|---|---|---|---|---|
  | 0.10 | code / GSM8K / prose | 1.52 / 1.44 / 1.21 | 1.92 / 1.72 / 1.27 | 2.17 / 1.81 / 1.24 | 2.41 / 1.76 / 1.11 |
  | 0.20 | code / GSM8K / prose | 1.40 / 1.33 / 1.12 | 1.66 / 1.49 / 1.10 | 1.79 / 1.49 / 1.02 | 1.84 / 1.34 / 0.84 |
  | 0.35 | code / GSM8K / prose | 1.26 / 1.19 / 1.00 | 1.38 / 1.24 / 0.92 | 1.41 / 1.18 / 0.80 | 1.35 / 0.99 / 0.62 |

  The table answers how many tokens to draft only once c and the profiles are measured. This change measures them.

## Goals / Non-Goals

**Goals:**
- Measured c(k), acceptance per position on four content kinds, the output verdict and the memory verdict, all under SSD streaming on the owner's M5 Max.
- One go or no-go with its numbers, and the defaults `320` starts from.

**Non-Goals:**
- Any code in the engine tree, or a port.
- Resident runs: this child does not run them.
- Server, exact sampling and TP (`340`, non-goal).

## Decisions

### D1. Measure on #1073's own tree
- **Why this tree.** Its scratch build, with one patched line, is the cheapest path to real numbers.
- **What carries over.** Its plain streaming decode lacks main's decode work since `0aaea5a` (`210`, `220`, `268`, ...), so its absolute rates are not this child's. Only c, in milliseconds, and the acceptance carry over, through D6.
- **Fallback** if the PR fails under streaming for reasons beyond the gate (for example, a verify MoE with no streaming path in that tree):
  - Take a scratch build of main with the streaming exclusion of `ds41_sessions_batch_supported` removed.
  - Run `session_concurrency_bench` with 2..6 sessions on the same prompt. Independent rows select more distinct experts than consecutive tokens of one session do.
  - The result is an upper bound of c on the child itself. Acceptance then waits for the port.

### D2. Four content kinds
The harness decodes prose, but DSpark's gain depends on content. Four fixed prompt files are recorded with their SHA-256:
- **code:** a C source of this tree, continued;
- **prose:** `speed-bench/promessi_sposi.txt`, as the harness uses;
- **chat:** a chat-templated question answered in prose;
- **tool:** a chat-templated request answered with a tool call.

Code and prose run at the harness frontiers 2048 and 8192, and chat and tool at their own length. All runs are greedy.

### D3. Output: rows first, then tokens
- **Row level.** A scratch dump gives the logits of every verify row for the first 64 cycles. A plain run with the same prefix gives the one-row logits at the same positions, and the two are compared bitwise.
- **If they differ,** the PR's switches are tried one family at a time, starting with the MMA rows off, to find a row-invariant configuration.
- **Token level.** Greedy 1024 tokens with and without `--dspark` on the parity prompts and the four kinds, recording the first differing position.

The outcomes:
- **Bitwise:** `320`'s spec requires identical output.
- **Bitwise only in a reduced configuration:** `320` takes only those kernels, and c is the one measured in that configuration.
- **No configuration is bitwise:** stop and ask the owner. The project rule rejects a speedup that changes greedy output.

### D4. c by forced length
- Each k in 1..5 is forced with cap k and confidence 0, so every cycle drafts exactly k.
- `c(k) = (t_cycle(k) - t_draft - t_decode) / (k t_decode)`, at 2048 and 8192, taken from the PR's timing counters or scratch timers.
- Each cycle is split into GPU, CPU waits and miss reads, so the miss share can be checked against D5's replay.

### D5. Memory
- **Timeline.** The `225` timeline (`vm_stat` at 1 Hz, `footprint` every 3 s) with the drafter beside `82GB` at a 32768 context. It passes with:
  - zero swapouts;
  - no compressed engine pages;
  - at least 18 GiB available to macOS (`270`'s frame).
- **Replay** of the `225` decode dump, which the `225` scratch build regenerates if it is gone:
  - with the cache shrunk by the drafter's slots (7.42 GiB / 9.49 MiB, about 800; a Q2 drafter is estimated at about 4 GiB, about 430 slots);
  - for the union of the experts of k+1 consecutive tokens per verify cycle.

  This gives the miss term of c, and what taking the drafter's memory out of the cache would cost.

### D6. Projection in milliseconds
- An extra row's cost is mostly GPU work and union misses, which do not shrink because this child's plain token is faster.
- The projection therefore carries Δ in ms from the PR and divides it by main's decode token time: `c_child = Δ_ms / 34 ms` at 2048. This is conservative.
- The gain is then the model with the measured acceptance, averaged over the k distribution the confidence head chose.

### D7. The gate
**Go to `320`** when all of these hold:
1. **Output.** D3 is bitwise in at least one configuration, and greedy tokens are identical on every prompt.
2. **Code.** The projected decode gain is at least +25% at 2048 and at 8192.
3. **Prose.** With back-off, the decode change has no CI wholly below zero. If it has one, the owner chooses between a stated tolerance for the opt-in flag and `330`'s stricter back-off first.
4. **Memory.** D5 passes with the chosen drafter file.
5. **Verify cost.** c(3) ≤ 0.3 in the projection.

**The other outcomes:**
- **Code +10..25%:** the owner decides.
- **Memory fails but c is low:** `350` first, which has no weights.
- **Under +10%, or output fails:** stop. The DSpark lines become `history` with the condition named.

### D8. The drafter file
- **For this change,** kernelpool's MXFP4 file. It is built from the official weights with the PR's own converter.
- **For `320`:**
  - If the file passes D5, `320` uses it.
  - Otherwise our own conversion goes first: the `mtp.*` shards of `deepseek-ai/DeepSeek-V4.1-Flash` through the PR's `deepseek41_quantize.py --dspark-out`, in a `mktemp` virtual environment.
  - A smaller quant is `330`'s work.
  - A file of our own needs a host the owner publishes to. That is the owner's step, outside the engine tree.

## Risks / Trade-offs

- **[The PR under streaming breaks beyond the gate]** → D1's fallback bounds c on main, and the acceptance waits for the port.
- **[kernelpool's file does not load at `cad7933`]** → The PR's converter is authoritative. Converting ourselves needs the owner's approval for the shards (about 7.4 GiB) and a temporary environment.
- **[Thermal drift between arms]** → ABBA order, and the harness's preflight conditions (AC power, nominal thermal state, GPU temperature under 60 °C) checked by hand before each block.
- **[The PR's plain decode is slower than main's]** → D6 carries milliseconds, not ratios.
- **[The GSM8K profile is a reported low]** → It is only a prior. D2's kinds replace it.
