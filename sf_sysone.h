/* System One readout: typed decisions read from next-token logits, no decode.
 * Uses only the public ds4.h API. See docs/system-one.md. */
#ifndef SF_SYSONE_H
#define SF_SYSONE_H

#include <stddef.h>
#include "ds4.h"

#define SF_SYSONE_MAX_OPTIONS 26
#define SF_SYSONE_TEMPLATE_VERSION 1
/* Top-two option logit gap under which a different prefill schedule can change
 * the answer: the 95th percentile of the gap change between the layer-major and
 * the token-major schedule, 100 decisions (sysone-bench/record.md, schedule
 * stability, 2026-11-12). */
#define SF_SYSONE_DELTA95 1.41

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
    double ms;           /* this question: restore, suffix eval and readout */
    int unstable;        /* top-two raw logit gap under SF_SYSONE_DELTA95 */
} sf_sysone_answer;

typedef struct sf_sysone sf_sysone;   /* symbol token tables, built once */

int  sf_sysone_open(sf_sysone **out, ds4_engine *e, char *err, size_t errlen);
void sf_sysone_close(sf_sysone *so);

/* Tokens of the state prefix. Appends to `out`. */
void sf_sysone_state_prefix(sf_sysone *so, const char *state, ds4_tokens *out);
/* Tokens of one question suffix. Appends to `out`. */
void sf_sysone_question_suffix(sf_sysone *so, const sf_sysone_question *q, ds4_tokens *out);

/* Token id of option i's symbol for question type `type` (A-Z or 0-9). */
int sf_sysone_symbol_token(const sf_sysone *so, sf_sysone_type type, int i);

/* Answer the questions from a session already synced to `prefix`
 * (ds4_session_tokens(s) equals prefix). `snap`, when not NULL, is a snapshot
 * of exactly that state and is used for the restores; when NULL and
 * n_questions > 1 the function takes its own. */
int sf_sysone_answer_from(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                          const ds4_session_snapshot *snap,
                          const sf_sysone_question *q, int n_questions,
                          const double *temperature, sf_sysone_answer *answers,
                          char *err, size_t errlen);

/* As sf_sysone_answer_from, but question k's suffix is suffixes[k] (tokens
 * after `prefix`) instead of the template's (835 live layout). */
int sf_sysone_answer_suffixes(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                              const ds4_session_snapshot *snap,
                              const sf_sysone_question *q, int n_questions,
                              const ds4_tokens *suffixes,
                              const double *temperature, sf_sysone_answer *answers,
                              char *err, size_t errlen);

/* 835: the text of a question asked as the next user turn of a conversation
 * (options and instruction line as the template). Caller frees. */
char *sf_sysone_turn_text(const sf_sysone_question *q);

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

#endif
