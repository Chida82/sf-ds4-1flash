# Design

Depends on `810` and `820`. Applies to `state_first`; under `schema_first`
(`a015`, if kept) the same trie hangs after the pointer prefill.

## Prompt

Option lines become `"[" k "] " LINE "\n"` with k decimal from 0; the
instruction line stays. The `a000` template (version 2) has no answer
prefill: a letter is read right after `</think>`. A big choice adds its own
prefill, `[`, after the assistant prefix (`BIG_PREFILL`), so the id is the
first thing the answer can say; a candidate is the text `k]`. Big choices
always take the version-2 suffix shape, whatever `--sysone-template` says:
they did not exist under version 1, so there is nothing to keep bitwise.

## Trie

For each k, tokenize `PREFILL + k + "]"` and `PREFILL` alone; the candidate's
token path is the tail after the prefill's tokens (assert the head matches;
on mismatch fail the request with a 500 that names k: do not guess). Insert
the paths in a trie keyed by token id. Because every candidate ends in `]`,
no candidate's text is a prefix of another's; assert that no path is a prefix
of another path.

With a digit-level tokenizer, 100 options give a root with children `0`-`9`,
each with children `]` and `0`-`9`; with a tokenizer that has multi-digit
tokens the trie is shallower. The code does not care which: it follows the
tokenizer.

## Evaluation

Definitions: at a node, `m` = the sum of the full-vocabulary probabilities of
its children's tokens; a child's conditional is `p(child) / m`. A leaf's
probability is the product of the conditionals on its path
(the paper's tree-factorized form). A node with one child has conditional 1
and is **not evaluated**.

```
state: session synced to prefix + suffix (the root readout position)
root_snap = save snapshot                  (only if some non-root node needs evaluation)
read children of root: ds4_session_token_logprob for each child token
frontier = non-leaf children with >= 2 children and path probability >= 1e-4
for node in frontier (highest path probability first):
    load root_snap
    for token on node's path: ds4_session_eval(s, token)     (31 ms each)
    read its children; push qualifying children to the frontier
```

A node not expanded because it is under the threshold gives its remaining
probability to its leaves in equal shares (it is at most 1e-4 in total per
node; this keeps the result a distribution).

`legal_mass` is the root's `m`. The per-option `logit` field is not defined
for trie answers; `sf.debug` returns `log p` per option instead.

Cost, digit tokenizer: n ≤ 100 → at most 9 evaluated nodes of depth 1, so
9 × (restore + 31 ms) ≈ 0.4 s worst case, and typically 1-3 because the
threshold prunes. n = 255 → up to 9 + 16 nodes ≈ 1 s worst case.

Depth-2 nodes need two forced tokens after the restore; evaluating them from
their parent's state would save one token but needs a snapshot per parent.
Do the simple version; revisit only if the bench shows large choices matter.

## Answer struct (as built, 2026-11-24)

`SF_SYSONE_MAX_OPTIONS` stays 26: the letter readout. `SF_SYSONE_MAX_CHOICE`
(255) sizes the answer's `logit` and `p` arrays, so a big choice uses the
same `sf_sysone_answer` and the same `sf_sysone_answer_from` path (12 bytes
per option, about 3 KiB per answer). For a big choice `logit[k]` holds
`log p_k` from the trie, and `sf_sysone_finish` applies the temperature as
for letters: `softmax(log p / T)` is exactly `p^(1/T)` renormalized. The
answer gains `evaluated_nodes` (0 on the letter path).

The trie math is `sf_sysone_trie_probs(paths, lens, n, read, ud, ...)`: the
readout is a function pointer, so the model-less tests drive it with a fake.
The model's readout restores a snapshot of the root (saved on the first node
below it) and evaluates the node's path tokens. A big choice on a live state
(`sf.state: "messages"`) is refused: its suffix comes from the conversation
turn, which has no `[` prefill.

Known loss: the model may reach the same text through another tokenization
(`12` as one token where the canonical path is `1`,`2`). Only the canonical
path is scored. `legal_mass` at the root shows how much probability the
canonical first tokens hold; the bench reports it.

## Server

`choice.criteria` accepts 1-255 entries; 27 or more go to
`sf_sysone_big_choice`. The response shape is unchanged (`choice`,
`confidence`, `probabilities` with every option). The `sf` object adds
`"evaluated_nodes"`.

## Bench

Banking77 (77 intents) from system-one-bench, the same suite `a010` rebuilds
(`convert.py --source s1b --suite banking77`, hash-checked against its
`data.lock.json`; its 77 option names are every `label_text` of the split,
sorted, so the whole test split is fetched). 200 items with published figures
beside: Jev 1.13.0 0.795, Mammoth-1 (Qwen3.5-27B) 0.945, Laya Router 0.440,
best Clef Flash 0.985. Run all 200 in `sysone` mode. Record accuracy, legal mass,
p50 latency, mean evaluated nodes. No acceptance threshold on accuracy: the
number is the result. The change is kept if the model-backed tests pass and
p50 latency per decision is under the suffix time plus 1 s.

## Tests

Model-less: trie built from hand-written token paths (digit-level and
multi-digit cases); renormalization on fixed probabilities (hand-computed for
a 12-option trie); a single-child node is not evaluated; the threshold
redistribution sums to 1.

Model-backed (`make test-sysone`): a 40-option choice whose options are the
numbers' names in Italian ("uno".."quaranta") and the state "Il numero scelto
è ventisette." → top is option 26 (0-based); probabilities sum to 1 within
1e-9; the same request twice is equal; a 26-option choice still takes the
letter path and matches its `800` bits.
