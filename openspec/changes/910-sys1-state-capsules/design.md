# Design

Depends on `800`, `820`. The payload layout is in `865`'s design (assert the
header the same way). After the 40 windows the payload holds, for owner
i = 0..3 (layers 2, 8, 14, 20): compressed rows `live × 512` floats, index
keys `live × 128` floats, and **for i < 3 when pos is odd** two more spans of
512 floats (`previous_kv`, `previous_score`); `live = pos/2` for i < 3 and
`pos` for i = 3. Source of truth: `ds41_state_spans` in `ds4.c`. The splicer
recomputes the total size from this formula and refuses a payload whose
length differs.

## Rules a capsule must obey

1. **Bound to a slot.** A capsule is (segment tokens, absolute start
   position, what preceded it). It can only be placed at that start.
2. **Even starts and even lengths**, so the two-token pairs of layers 2-19
   align. Use even total positions at every capture so no pending pair is in
   play.
3. **The token block must be rewritten too**, and the splice must be proved
   to have taken: before the suffix sync assert
   `ds4_session_common_prefix(s, &prompt) == spliced_len`. Otherwise the
   engine silently discards the state and prefills everything jointly, and
   the test reports perfect agreement while measuring nothing.
4. **Windows are not spliced.** The 40 ring windows always come from the
   payload being loaded (they describe its last 128 positions).

## Stage 1 experiment (`sf_splice.c`)

Items: 60 two-segment decisions `[base][A][B] + question`, A and B each
300-600 tokens (inside 128 tokens everything is raw window and nothing is
tested), from `820`-style content; mark each item as "needs both segments"
or "one segment answers". Pad A to an even length with a newline token.

Per item:

```
J = snapshot after sync([base][A][B])                       /* joint: the reference */
F = snapshot after sync([base][filler × len(A)][B])         /* filler = repeated "\n" tokens */
S = copy of F; for each owner copy J's rows of A's range over F's; rewrite A's token ids
load S; assert common prefix; sync(+ question suffix); read option logits  -> spliced
load J; sync(+ question suffix); read                                       -> joint
load F; sync(+ question suffix); read                                       -> filler (the "A missing" control)
```

A's range: owners 0-2 rows `[start/2, (start+len)/2)`, owner 3 rows
`[start, start+len)`.

Free correctness check: owner 0's rows for B positions beyond the first 254
tokens of B must be **bitwise equal** between J and F (they depend only on
the preceding 254 tokens). If they are not, the splicer's offsets are wrong.

Noise floor: also `J' = sync([base][A])` then `sync(+[B])`. J and J' differ
only by schedule; report agreement(J, J').

Report: argmax agreement spliced-vs-joint, mean KL over options, legal mass,
split by the two item kinds; the same for filler-vs-joint (it must be clearly
worse on items needing A, or the items do not test anything).

| Result | Next |
|---|---|
| spliced-vs-joint agreement within 2 points of the noise floor on both kinds | Stage 2 |
| fine on "one segment answers", more than 5 points worse on "needs both" | Record it; propose capsules only for independent documents; ask the owner |
| worse than 90% overall | Stop; record under "Considered and not proposed" |

About 180 sweeps, 20 minutes.

## Stage 2 (by the gate): fixed slots

Layout `[base][slot 1 padded to S1][slot 2 padded to S2]…[schema][pointer
suffix]`, padding with the filler token. Each capsule is encoded once per
slot it may occupy, after the true base and filler for earlier slots. The
first slot is an exact prefix (it is `830`). Padding rows stay visible to
the model and consume context: report their effect by running Stage 1's
metric with padded slots.

Server: a capsule store keyed by (model file, template version, slot, segment
tokens), separate from `830`'s cache and from the disk KV store; a composed
state is never stored anywhere. Request form and limits are designed only
after Stage 2's numbers exist; do not design them here.
