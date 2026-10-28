# Proposal

## Why

A second draft source needs no weights and no memory. It finds the last few generated tokens earlier in the context and proposes what followed them there. Agent work repeats its context: code edits that copy most of a file, tool results quoted back, and long identifiers. #1167 does this for V4 Flash on the DSpark verifier, and measured on the M5 Max, Q2:
- +19% greedy decode on a code-shaped prompt;
- -0.7..-2.4% on sparse prose.

This change is conditional, and runs in one of two places:
- **Before `320`**, if `310` finds verify cheap (c low) but the drafter's memory too costly. It then brings the verifier and rollback with this drafter instead of DSpark's. The number moves before `320`.
- **After `320`**, as a second source on the same verifier, only if an agent-replay kind shows prompt lookup beating DSpark alone.

## What Changes

- **Prompt lookup.**
  - The most recent earlier occurrence of the last n = 3 tokens in the session's context, and the tokens that followed it, up to the draft cap.
  - Opt-in with `--ngram-spec N`, upstream's name from #1167, in the CLI, the bench and (after `340`) the server.
  - Greedy, like `320`. After `340`, a sampled cycle treats a lookup draft as a proposal with probability one. Exact sampling then accepts each token with the target's probability of it, which keeps the distribution.
- **Combined with DSpark** (the after-`320` case). Each cycle takes the longer of the two proposals: the lookup draft and DSpark's confident prefix. If `330` S4 made the expected-cost rule the default, it takes the one with the higher expected tokens per time instead, pricing the lookup by its own running acceptance. Either way, the chosen proposal is verified by the same rows.
- **Harness, tool step.** An `agent-replay` decode kind: a prompt holding a source file, then a request to rewrite part of it, so the answer copies from context.
- **Back-off** is shared with DSpark (`330` S3).
- **Registry.** #1167 is `idea -> 350`. Its V4 Flash code is not ported.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `dspark-drafting`: a weightless prompt-lookup draft source, alone or combined with DSpark, under the same output rules.

## Impact

- `ds4.c`: the lookup over the session's token history, and the source choice in the cycle.
- `ds4_cli.c`, `ds4_bench.c`, then `ds4_server.c`.
- `speed-bench/ab_bench.py` and its text (the `agent-replay` kind).
- `README.md`, `docs/upstream-prs.md`.
- If it runs before `320`: everything `320` lists for the verifier, the rollback and the streaming rows, without the support file and its memory.
