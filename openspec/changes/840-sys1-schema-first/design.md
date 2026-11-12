# Design

Depends on `830` (cache code, `sf_sysone_answer_from`) and `820` (bench).

## Layout

Every piece tokenized on its own and appended, as in `800`.

Schema prefix:

1. `ds4_chat_begin`
2. system message, `SYS2 = "You are a decision function. Several questions are defined below, then a state. For the question you are asked about, choose exactly one of its listed options."`
3. user marker (`ds4_token_user`)
4. `"Questions:\n"`
5. per question i (1-based), one block:
   `"Q" i ": "`, instructions, `"\nOptions:\n"`, the option lines exactly as
   in `800` (`"[A] name: text\n"`, digits for `score`), then `"\n"`

→ **schema snapshot point**

6. `"State:\n"`, then the state text

→ **state snapshot point**

Pointer suffix for question i:

1. `"\n\nAnswer Q" i "."`
2. `ds4_chat_append_assistant_prefix(e, &t, DS4_THINK_NONE)`
3. `"Q" i ": ["`

`sf_sysone_open` gains the same in-context symbol check for this prefill:
tokens of `"Q1: [" SYMBOL "]"` must be the tokens of `"Q1: ["` followed by
the symbol's token. Check with i = 1 and i = 12 (one and two digits).

Question order in the schema is the request's key order. Two requests with
the same questions in a different order have different schemas; that is
accepted and documented (callers keep a stable order to hit the cache).

Limit: 64 questions; a schema of 256 tokens or more is prefilled by a sweep
(6-7 s, once per schema).

## Interface

```c
typedef enum { SF_SYSONE_STATE_FIRST, SF_SYSONE_SCHEMA_FIRST } sf_sysone_layout;

void sf_sysone_schema_prefix(sf_sysone *so, const sf_sysone_question *q, int n, ds4_tokens *out);
void sf_sysone_schema_state(sf_sysone *so, const char *state, ds4_tokens *out);   /* step 6 */
void sf_sysone_pointer_suffix(sf_sysone *so, int index1, ds4_tokens *out);
```

`sf_sysone_answer_from` gains a `layout` argument and builds either the
question suffix or the pointer suffix; everything after the suffix (readout,
`sf_sysone_finish`) is shared.

## Server flow for `schema_first`

```
S = schema prefix tokens
schema cache: exact lookup on S  -> load snapshot | sync(S) and store
P = S + schema_state(state)
ds4_session_sync(s, P)           -> prefills only the state
snapshot (when more than one question)
for each question: restore, sync(P + pointer suffix), readout
```

The schema cache reuses `830`'s entry type and eviction, in a second array
(`--sysone-schema-cache N`, default 8; it shares the byte budget). The state
cache of `830` is not used in this layout: here the state is the variable
part. (A state that repeats *with the same schema* could be cached too; add it
only if a bench scenario asks for it.)

Cost model to verify, with a 60-token schema per question, three questions,
a 600-token state:

| Layout | First request | Next state, same schema |
|---|---|---|
| `state_first` | 6.5 s + 3 × 1.9 s = 12.2 s | the same, 12.2 s |
| `schema_first` | 5.6 s (schema, token by token) + 6.5 s + 3 × 0.25 s = 12.9 s | 6.5 s + 0.75 s = 7.3 s |

and for a 100-token state (token by token): 3.1 s + 0.75 s = 3.9 s against
3.1 s + 5.7 s = 8.8 s. Replace these estimates with measured rows.

## Prior correction

At the schema snapshot point, once per schema entry:

```
restore schema snapshot
sync(S + schema_state("(no state given)"))
for each question i: sync(+ pointer suffix i); prior_i[k] = logit of option k; restore
```

Stored in the schema entry as `float prior[n_questions][26]`. Cost: one short
state and one pointer suffix per question, once per schema.

At request time, when `sf.prior_correction` is true:
`logit'[k] = logit[k] − (prior_i[k] − mean_k prior_i[k])`, then
`sf_sysone_finish` as usual. `legal_mass` stays the uncorrected one. The
`sf` response object reports `"prior_correction":true`.

Not applied to `score` (an ordinal prior is information, not bias) unless the
bench shows it helps there too.

## Acceptance (bench, `typed-decisions` test split and `fixtures-it.jsonl`)

Group the items into requests of up to 5 questions per state where the set
allows; where items have one question each, group items that share a
question into one schema and send their states one by one.

`schema_first` is kept (documented as supported) when, against `state_first`
on the same items:

- accuracy difference: the bootstrap 95% interval of
  (`schema_first` − `state_first`) does not lie wholly below −1 point;
- median latency per decision on the "next state, same schema" scenario is at
  most half.

Prior correction is kept when, against the uncorrected `schema_first` run, the
flip rate under `--rotate 1` falls and accuracy does not fall (same interval
rule). Otherwise delete the code and record a rejected row.

A failed acceptance of the layout itself: keep the code out, record the
numbers in `sysone-bench/record.md` and `docs/system-one.md`.

## Tests

Model-less: token construction of the schema prefix is a token-prefix of
prefix+state, which is a token-prefix of the full prompt (with a stub
tokenizer this is not checkable; do it in the model-backed test).

Model-backed (`make test-sysone`): the in-context symbol check for the
pointer prefill; the 12 fixtures of `800` as four requests of three questions
give the expected tops; the same request twice is bitwise equal; a second
state on a cached schema reports a schema hit and prefills only the state.
