# Design

Read `docs/system-one.md` first (sections 3 and 6 define the words used here).

## Files and naming

New files use the `sf_` prefix (`sf_sysone.c`): they are this child's own, and
the `ds4_` prefix is reserved for files upstream owns (a future upstream file
of the same name would otherwise collide at a sync). `sf_sysone.c` includes
only `ds4.h` and libc. It MUST NOT include or declare anything from `ds4.c`
internals.

## Public interface (`sf_sysone.h`)

```c
#define SF_SYSONE_MAX_OPTIONS 26
#define SF_SYSONE_TEMPLATE_VERSION 1

typedef enum { SF_SYSONE_NOUL, SF_SYSONE_CHOICE, SF_SYSONE_SCORE } sf_sysone_type;

typedef struct {
    sf_sysone_type type;
    const char *instructions;        /* never NULL; "" allowed */
    int n_options;                   /* noul: 2. choice: 1..26. score: 1..10 */
    const char *const *option_names; /* choice: n names. noul, score: NULL */
    const char *const *option_texts; /* n entries; an entry may be NULL */
} sf_sysone_question;

typedef struct {
    int n_options;
    float logit[SF_SYSONE_MAX_OPTIONS];  /* raw logit of each option symbol */
    double p[SF_SYSONE_MAX_OPTIONS];     /* softmax over the options, after temperature */
    double legal_mass;   /* sum over options of the full-vocabulary probability */
    int top;             /* index of the largest p; ties go to the lowest index */
    double confidence;   /* choice and score: Jev formula. noul: |2p-1| */
    double value;        /* noul: p[0] (yes). score: sum i*p[i]. choice: p[top] */
    int suffix_tokens;
} sf_sysone_answer;

typedef struct sf_sysone sf_sysone;   /* symbol token tables, built once */

int  sf_sysone_open(sf_sysone **out, ds4_engine *e, char *err, size_t errlen);
void sf_sysone_close(sf_sysone *so);

/* Tokens of the state prefix. Appends to `out`. */
void sf_sysone_state_prefix(sf_sysone *so, const char *state, ds4_tokens *out);
/* Tokens of one question suffix. Appends to `out`. */
void sf_sysone_question_suffix(sf_sysone *so, const sf_sysone_question *q, ds4_tokens *out);

/* Prefill the state, then answer every question in its own branch.
 * `temperature` divides the option logits (1.0 = raw). Returns 0 on success.
 * `prefix_tokens` (may be NULL) receives the state prefix length. */
int sf_sysone_decide(sf_sysone *so, ds4_session *s, const char *state,
                     const sf_sysone_question *q, int n_questions,
                     const double *temperature /* per question, or NULL */,
                     sf_sysone_answer *answers, int *prefix_tokens,
                     char *err, size_t errlen);

/* Pure math, no engine: fills p, top, confidence, value from logit[]. */
void sf_sysone_finish(sf_sysone_type type, double temperature, sf_sysone_answer *a);
```

## Prompt layout (template version 1)

Every piece below is tokenized **on its own** and appended to the token
array (`ds4_tokenize_text` appends; it never resets `out`). Never build one
string and tokenize it whole: BPE would merge across the boundary between
state and question, and the state prefix would stop being a token prefix of
the full prompt.

State prefix, in order:

1. `ds4_chat_begin(e, &t)`
2. `ds4_chat_append_message(e, &t, "system", SYS)` with
   `SYS = "You are a decision function. Read the state and answer the question by choosing exactly one of the listed options."`
3. `ds4_tokens_push(&t, ds4_token_user(e))`
4. `ds4_tokenize_text(e, "State:\n", &t)`
5. `ds4_tokenize_text(e, state, &t)`

The prefix ends right after the state text. Nothing follows it, so a longer
state that extends this one is still a token-prefix extension (`830` relies on
this).

Question suffix, in order:

1. `"\n\nQuestion: "`, then `instructions`, then `"\nOptions:\n"`
2. one piece per option: `"[" SYMBOL "] " LINE "\n"` built as one string
3. `"Select one option. Answer only with its bracketed identifier."`
4. `ds4_chat_append_assistant_prefix(e, &t, DS4_THINK_NONE)` (assistant
   marker and `</think>`)
5. the answer prefill, `"Best answer: ["` unless the probe below picks another

SYMBOL and LINE per type:

| Type | Symbols | LINE of option i |
|---|---|---|
| `choice` | `A`..`Z` in order | `name` when the text is NULL or empty, else `name: text` |
| `noul` | `A`, `B` | `A`: `Yes` or `Yes: text`; `B`: `No` or `No: text` (texts are `criteria.true` / `criteria.false`) |
| `score` | `0`..`9` in order | the level text |

`score` uses digits because the position is the score and the digit shows the
order; `noul` uses letters, not the words true/false, because Laya's card
reports a model following the labels instead of the state.

## Symbol tokens (`sf_sysone_open`)

For each of the 36 symbols (A-Z, 0-9):

1. Tokenize the symbol alone. It MUST be exactly one token; keep its id.
2. Tokenize `"Best answer: ["` (call the result P) and
   `"Best answer: [" SYMBOL "]"` (call it F). F MUST start with all of P and
   F's next token MUST be the id from step 1. This proves the model, writing
   the answer naturally, would emit exactly that token after the prefill.

On any failure return an error naming the symbol and both token lists. Do not
work around it silently: the fix is another prefill (see the probe).

## Readout

After `ds4_session_sync` reaches the end of a suffix, for each option i call
`ds4_session_token_logprob(s, id_i, &sc)`: `sc.logit` is the raw logit,
`sc.logprob` the log-probability under the full vocabulary. Then:

- `legal_mass = Σ exp(sc.logprob)` over the options.
- `sf_sysone_finish`: `p = softmax(logit / T)` over the options (subtract the
  maximum before `exp`); `top`; then
  - `choice`: `confidence = (p_top − 1/n) / (1 − 1/n)`, and 1 when n is 1.
  - `score`: `m = top`; `MAD = (1/n) Σ |i − (n−1)/2|`;
    `confidence = max(0, 1 − Σ p_i·|i − m| / MAD)`, and 1 when n is 1;
    `value = Σ i·p_i`.
  - `noul`: `value = p[0]`; `confidence = |2·p[0] − 1|`.

A question with one option is answered without touching the session:
`p[0] = 1`, `legal_mass = 1`.

## Branching (`sf_sysone_decide`)

```
refuse if ds4_session_steering(s)            -> "system one needs an unsteered session"
prefix = state prefix tokens
ds4_session_sync(s, prefix)                  -> state prefill
if n_questions > 1: ds4_session_save_snapshot(s, &snap)
for k in 0..n-1:
    if k > 0: ds4_session_load_snapshot(s, &snap)
    full = prefix + suffix(k)
    refuse if full.len >= ds4_session_ctx(s) -> "max_tokens_exceeded"
    ds4_session_sync(s, full)                -> evaluates only the suffix
    readout
ds4_session_snapshot_free(&snap)
```

After `ds4_session_load_snapshot`, `ds4_session_pos(s)` MUST equal
`prefix.len` and `ds4_session_checkpoint_valid(s)` MUST be true; assert both
(the test checks them too). `ds4_session_rewind` is not an alternative: it
invalidates the checkpoint because the compressors cannot be truncated.

The session is left at the end of the last question's suffix. The caller owns
what happens to it next.

Cost, from `docs/MODEL_KNOWLEDGE.md`: the state costs 31 ms per token under
256 tokens and one 6-7 s sweep from 256 to about 2000; a suffix under 256
tokens costs 31 ms per token. A suffix of 256 tokens or more becomes a sweep
(6 s): legal, slow, and logged once per request on stderr.

## Template probe (run once, model-backed)

`tests/test_sysone --probe` evaluates the 12 fixture questions below with
three answer prefills and prints, per prefill, the mean and minimum legal mass
and how many fixtures have the expected top option:

| Id | Assistant prefill | Option line | Instruction line |
|---|---|---|---|
| T-A | `Best answer: [` | `[A] text` | as above |
| T-B | `[` | `[A] text` | as above |
| T-C | (empty: read right after `</think>`) | `A. text` | `Answer with the identifier only.` |

Pick the prefill with the most correct fixtures; break a tie by the higher
mean legal mass. Freeze it as template version 1, delete the other two from
the code (the probe mode stays, reading its candidates from a table in the
test, not from the module), and record the three rows in
`docs/system-one.md` under a new "Template" section. If no candidate reaches
mean legal mass 0.5, stop and ask the owner.

Fixtures (state → question → expected top). Six English, six Italian:

1. "My package arrived broken and I want my money back." → choice
   {refund_request, shipping_question, praise} → refund_request
2. same state → noul "The customer is satisfied." → `value < 0.5`
3. same state → score ["very negative","negative","neutral","positive","very positive"] → top ≤ 1
4. "Meeting moved to Thursday 3pm, room B." → noul "The meeting is on Thursday." → `value > 0.5`
5. "Server CPU at 97% for 20 minutes, three alerts fired." → choice {ignore, monitor, page_oncall} → page_oncall
6. "The invoice total is 1,250 EUR, due on the 30th." → noul "The invoice is overdue." → `value < 0.5`
7. "Il pacco è arrivato rotto e voglio il rimborso." → choice {richiesta_rimborso, domanda_spedizione, complimento} → richiesta_rimborso
8. same state → noul "Il cliente è soddisfatto." → `value < 0.5`
9. "Grazie mille, servizio perfetto e consegna in anticipo!" → score ["molto negativo","negativo","neutro","positivo","molto positivo"] → top ≥ 3
10. "La riunione è spostata a giovedì alle 15." → noul "La riunione è di giovedì." → `value > 0.5`
11. "Ho dimenticato la password e non riesco ad accedere." → choice {problema_accesso, fatturazione, altro} → problema_accesso
12. "Vorrei disdire l'abbonamento da fine mese." → choice {disdetta, upgrade, reclamo} → disdetta

## Tests

Model-less, in `make test` (`./tests/test_sysone`):
- `sf_sysone_finish` on fixed logits: the `score` example (0, 0.57, 0.43)
  gives confidence 0.35 ± 0.01; `choice` with p = (0.92, 0.05, 0.03) gives
  0.88; one option gives 1; equal logits give confidence 0; temperature 2
  flattens and keeps `top`.

Model-backed, `make test-sysone` (pattern: `test-deepseek41-steering-session`
in the `Makefile`; engine opened as `tests/test_deepseek41_graph.c` opens it,
with SSD streaming and a cache of at most 32 GiB):
- symbols: `sf_sysone_open` succeeds.
- fixtures: all 12 expected tops; every legal mass printed.
- **isolation**: fixture 1 asked alone, and asked as the third of three
  questions, gives bitwise equal `logit[]`.
- **determinism**: the same request twice gives bitwise equal `logit[]`.
- after each `ds4_session_load_snapshot`: position and validity as above.
- prints prefix tokens, suffix tokens and milliseconds per phase.

A model-backed test prints one line per check that names it (`sysone:
isolation OK`), because an exit code alone proves nothing (StarForge rule 19).

## Risks

- The prefill may be off-distribution and spread probability outside the
  symbols. The probe measures it and the legal mass reports it per answer.
- Bitwise isolation depends on snapshot restore being exact for V4.1 under
  streaming. `tests/test_deepseek41_graph.c` already checks restore; if the
  isolation test fails, stop and report: do not loosen it to a tolerance.

## Probe result (2026-11-11)

The probe ran: all three candidates got 12/12, T-C had the highest mean legal
mass (1.0000 against T-A 0.9999 and T-B 0.1682). **T-C is template version
1**: option lines `A. text`, last instruction line `Answer with the identifier
only.`, no answer prefill (the symbols are read right after `</think>`). The
`Best answer: [` text in the sections above is the pre-probe default; the
symbol check at open uses the empty prefill, so it reduces to "one token".
Rows and timings: `docs/system-one.md` section 7.
