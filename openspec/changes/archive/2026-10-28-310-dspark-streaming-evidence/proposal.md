# Proposal

## Why

V4.1 Flash ships its own drafter. The official checkpoint carries it as `mtp.0-2`: DSpark, with three stages, a five-token block and a confidence head. Upstream ds4 refuses DSpark for V4.1. Open PR #1073 implements it on Metal, but only for resident weights: `ds41_draft_init` returns false under streaming. On an M3 Ultra, resident, it reports:
- +44% decode on code at 4K;
- +40..61% from 16K to 256K;
- -4..+1% on prose.

This child always runs under SSD streaming. Three things decide whether DSpark pays here, and none has been measured:
- **c, the cost of each extra verify row** relative to one decode token under streaming. It covers the experts of k+1 rows read and multiplied, and the drafter's 7.42 GiB competing with the expert cache.
- **The acceptance** of the V4.1 drafter against this child's Q2 target, on the owner's content: code, prose, chat and tool calls.
- **Whether verify rows can be bit-identical to one-row decode.** The project's output rule needs it: greedy tokens with the drafter must equal those without it.

DSpark is several weeks of porting. This change measures before anyone ports, and ends with a go or no-go for `320`.

## What Changes

Measurement only; nothing lands in the engine tree.

- **Scratch build of #1073** at `cad7933`, in a scratchpad clone of the upstream mirror, with the streaming gate of `ds41_draft_init` removed as a scratch patch.
- **The support GGUF.** `kernelpool/DeepSeek-V4.1-Flash-MXFP4-GGUF`, file `DeepSeek-V4.1-Flash-DSpark.gguf`, 7.42 GiB, downloaded into the shared Hugging Face cache once the owner approves.
- **Output.**
  - The logits of every verify row against one-row decode at the same position, bitwise.
  - Greedy tokens with and without `--dspark` on the parity prompts and on the four content kinds.
- **Verify cost.** The time of a verify cycle at k = 1..5 against one decode token, at 2048 and 8192, split into GPU, CPU waits and miss reads. This gives c(k), recorded as a curve (a file `330` can seed a cost model from), not only as a number.
- **Acceptance.** For each of four content kinds (code, the harness prose, chat, tool calls), at confidence 0.4, 0.6 and 0.8 and caps 2, 3 and 5:
  - acceptance per position;
  - mean accepted length;
  - mean drafted k.

  Plus one uncut cell per kind (confidence 0, cap 5) whose per-cycle log keeps the drafter's confidence at every position next to the accepted length.
- **Draft-length rule.** An offline replay of those uncut logs compares #1073's rule (the longest prefix whose per-position confidence passes a threshold, under a cap) with DeepInfer's expected-cost rule (the k that maximises expected tokens over expected cycle time, k = 0 included), and checks how well the confidence predicts acceptance on this Q2 target.
- **End to end on one binary.** Plain against `--dspark` decode, in ABBA order, per kind, at 2048 and 8192, including the scheduler's back-off on prose.
- **Memory.**
  - The `225` timeline with the drafter loaded beside `82GB`.
  - A replay of the `225` id dumps for two cases: the union of the experts of k+1 consecutive tokens, and the cache shrunk by the drafter's slots (about 800 at MXFP4).
- **Projection** of the gain onto this child's decode (29.6 tokens/s at 2048), from the measured c and acceptance.
- **Decision record.**
  - **Next step:** `320` (DSpark first), `350` first (n-gram on the same verifier), or stop.
  - **The drafter file:** kernelpool's file or our own conversion, MXFP4 or Q2.
  - **Defaults:** the draft cap and the confidence threshold.
  - **The draft-length rule** `330` S4 starts from: threshold and cap, or expected cost, with the replay's predicted difference.

## Capabilities

### New Capabilities
None (`skip_specs: true`): measurement only.

### Modified Capabilities
None.

## Impact

- `speed-bench/perf-record.md` (one section), and the c(k) curve as a small data file beside it.
- `docs/upstream-prs.md`: the DSpark commit lines of #1073 get the decision.
- `320`, `330`, `340` and `350` read their gates from this change.
- **The owner approves** the 7.42 GiB download and any temporary Python environment (only needed if the decision asks for our own conversion; it lives in a `mktemp` directory).
- About 8-9 hours of model runs, which can run unattended overnight under `caffeinate`. The scratch build stays in the scratchpad.
