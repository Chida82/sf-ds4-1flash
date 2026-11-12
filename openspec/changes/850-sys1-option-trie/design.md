# Design

Depends on `810` and `820`. Applies to `state_first`; under `schema_first`
(`840`, if kept) the same trie hangs after the pointer prefill.

## Prompt

Option lines become `"[" k "] " LINE "\n"` with k decimal from 0, the
instruction line stays, the prefill stays `Best answer: [` (the frozen one of
`800`). A candidate is the text `k]`.

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

## Answer struct

`SF_SYSONE_MAX_OPTIONS` stays 26 for the fixed arrays. A large choice returns
its probabilities in a heap array:

```c
typedef struct { int n; double *p; double legal_mass; int top; double confidence; int evaluated_nodes; } sf_sysone_big_answer;
int sf_sysone_big_choice(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                         const sf_sysone_question *q, double temperature,
                         sf_sysone_big_answer *out, char *err, size_t errlen);
```

Temperature: applied to the final distribution as `p_k^(1/T)` renormalized
(there is no single logit vector to divide).

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

Banking77 (77 intents, public; the paper reports 69.0% training-free for a 4B
model, Jev's third-party figure is 0.87, Laya's 0.43): `convert.py` gains a
converter; run 300 test items in `sysone` mode. Record accuracy, legal mass,
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
