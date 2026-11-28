/* System One readout: typed decisions read from next-token logits, no decode.
 * Uses only the public ds4.h API. See docs/system-one.md. */
#ifndef SF_SYSONE_H
#define SF_SYSONE_H

#include <stddef.h>
#include "ds4.h"

#define SF_SYSONE_MAX_OPTIONS 26  /* letter readout: one symbol token per option */
#define SF_SYSONE_MAX_CHOICE 255  /* a040: a choice above 26 options is read through a trie of "[k]" ids */
#define SF_SYSONE_TRIE_DEPTH 8
#define SF_SYSONE_TEMPLATE_VERSION 2 /* the default; 1 stays selectable (a000) */
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
    float logit[SF_SYSONE_MAX_CHOICE];  /* raw logit of each option symbol; a trie choice: log p of each id */
    double p[SF_SYSONE_MAX_CHOICE];     /* softmax over the options, after temperature */
    double legal_mass;   /* sum over options of the full-vocabulary probability */
    int top;             /* index of the largest p; ties go to the lowest index */
    double confidence;   /* choice and score: Jev formula. noul: |2p-1| */
    double value;        /* noul: p[0] (yes). score: sum i*p[i]. choice: p[top] */
    int suffix_tokens;
    double ms;           /* this question: restore, suffix eval and readout */
    double restore_ms;   /* a080: snapshot load and its checks; 0 for the first evaluated question */
    double eval_ms;      /* a080: ds4_session_sync of prefix + suffix */
    int unstable;        /* top-two raw logit gap under SF_SYSONE_DELTA95 */
    int evaluated_nodes; /* a040: trie nodes read (root included); 0 on the letter path */
} sf_sysone_answer;

/* a080: phases outside the questions, in milliseconds. */
typedef struct {
    double prefill_ms;  /* ds4_session_sync of the state prefix (sf_sysone_decide) */
    double save_ms;     /* ds4_session_save_snapshot; 0 with one question or a caller's snapshot */
} sf_sysone_timing;

typedef struct sf_sysone sf_sysone;   /* symbol token tables, built once */

/* template_version: 1 or 2 (SF_SYSONE_TEMPLATE_VERSION); any other id fails
 * with "unknown template version N". */
int  sf_sysone_open(sf_sysone **out, ds4_engine *e, int template_version, char *err, size_t errlen);
int  sf_sysone_template(const sf_sysone *so);
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
                          char *err, size_t errlen, sf_sysone_timing *timing /* may be NULL */);

/* As sf_sysone_answer_from, but question k's suffix is suffixes[k] (tokens
 * after `prefix`) instead of the template's (835 live layout). */
int sf_sysone_answer_suffixes(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                              const ds4_session_snapshot *snap,
                              const sf_sysone_question *q, int n_questions,
                              const ds4_tokens *suffixes,
                              const double *temperature, sf_sysone_answer *answers,
                              char *err, size_t errlen, sf_sysone_timing *timing);

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
                     char *err, size_t errlen, sf_sysone_timing *timing /* may be NULL */);

/* a040: probabilities of n token paths, read node by node. `read` fills prob[i]
 * with the full-vocabulary probability of tokens[i] after path[0..depth). A node
 * with one continuation is not read; a node whose path probability is under
 * 1e-4 is not expanded and shares it equally among its options. Fills logp[k]
 * (log probability of option k, the distribution summing to 1), the root's
 * legal mass and the number of nodes read. Fails when a path is empty, longer
 * than SF_SYSONE_TRIE_DEPTH, or a prefix of another. */
typedef int (*sf_sysone_trie_read)(void *ud, const int *path, int depth, const int *tokens, int n, double *prob);
int sf_sysone_trie_probs(const int *paths /* n x SF_SYSONE_TRIE_DEPTH */, const int *lens, int n,
                         sf_sysone_trie_read read, void *ud, float *logp, double *legal_mass,
                         int *evaluated, char *err, size_t errlen);

/* Pure math, no engine: fills p, top, confidence, value from logit[]. */
void sf_sysone_finish(sf_sysone_type type, double temperature, sf_sysone_answer *a);

#endif
