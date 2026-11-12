# Proposal

## Why

Jev accepts up to 255 options in a `choice`; `800` stops at 26 because it
reads one letter. Intent routing, taxonomy nodes and tool selection often
have more. The two open answers are:

- **JevK5**: groups of 16 options, `ceil(n/16) + 1` passes. Each pass repeats
  its options' text. At 31 ms per token that is the whole option list paid
  again, plus a final pass: about 40 s for 100 options of 10 tokens.
- **LLM-as-Jev**: number the options `[0]`..`[n−1]`, list them once, and score
  each id's token path `k]` by teacher forcing from one shared prefill. The
  extra cost is one token per *internal node* of the id trie.

Only the second fits this model: the option list is paid once, and a
100-option choice adds at most nine one-token evaluations (0.3 s).

## What Changes

- `choice` with 27-255 options uses numeric ids and a token trie built from
  the real tokenization of each `k]`.
- Path probabilities are renormalized over the legal children at each node,
  so a node with one child costs nothing.
- Branches whose probability is below a threshold are not expanded.
- The HTTP limit rises from 26 to 255. Choices of 1-26 options keep the
  letter readout and its bits.

## Non-goals

- No hierarchical or retrieval pre-filter (callers can walk a taxonomy with
  several requests, as Jev's docs suggest).
- No change to `score` or `noul`.

## Impact

- `sf_sysone.c/.h`: trie build, expansion, answer struct sized for 255.
- `ds4_server.c`: the limit and the response for large choices.
- Bench: a 77-option intent set (Banking77) for accuracy and latency.
