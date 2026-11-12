/* System One readout (change 800). Only ds4.h and libc: the engine sources
 * stay untouched, so upstream syncs never conflict here. */
#include "sf_sysone.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Template version 1 (docs/system-one.md, "Template"). */
static const char SYS[] =
    "You are a decision function. Read the state and answer the question by "
    "choosing exactly one of the listed options.";
/* Probe winner T-C: no answer prefill, the symbol is read right after </think>. */
static const char ANSWER_PREFILL[] = "";

#define N_SYMBOLS 36 /* A-Z then 0-9 */

struct sf_sysone {
    ds4_engine *e;
    int symbol[N_SYMBOLS];
};

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static char symbol_char(int k) { return k < 26 ? (char)('A' + k) : (char)('0' + k - 26); }

static void dump_tokens(sf_sysone *so, const ds4_tokens *t, char *buf, size_t len) {
    size_t used = 0;
    buf[0] = '\0';
    for (int i = 0; i < t->len && used + 1 < len; i++) {
        size_t n = 0;
        char *txt = ds4_token_text(so->e, t->v[i], &n);
        int w = snprintf(buf + used, len - used, "%s%d'%.*s'", i ? " " : "", t->v[i],
                         (int)n, txt ? txt : "");
        free(txt);
        if (w < 0) break;
        used += (size_t)w;
    }
}

int sf_sysone_open(sf_sysone **out, ds4_engine *e, char *err, size_t errlen) {
    *out = NULL;
    sf_sysone *so = calloc(1, sizeof(*so));
    if (!so) { snprintf(err, errlen, "out of memory"); return 1; }
    so->e = e;
    ds4_tokens p = {0};
    ds4_tokenize_text(e, ANSWER_PREFILL, &p);
    for (int k = 0; k < N_SYMBOLS; k++) {
        char sym[2] = {symbol_char(k), 0}, full[32];
        ds4_tokens alone = {0}, f = {0};
        ds4_tokenize_text(e, sym, &alone);
        snprintf(full, sizeof(full), "%s%s", ANSWER_PREFILL, sym);
        ds4_tokenize_text(e, full, &f);
        int ok = alone.len == 1 && ds4_tokens_starts_with(&f, &p) && f.len > p.len &&
                 f.v[p.len] == alone.v[0];
        if (ok) so->symbol[k] = alone.v[0];
        else {
            char a[256], b[512];
            dump_tokens(so, &alone, a, sizeof(a));
            dump_tokens(so, &f, b, sizeof(b));
            snprintf(err, errlen, "symbol %s is not one token after \"%s\": alone [%s], full [%s]",
                     sym, ANSWER_PREFILL, a, b);
        }
        ds4_tokens_free(&alone);
        ds4_tokens_free(&f);
        if (!ok) { ds4_tokens_free(&p); free(so); return 1; }
    }
    ds4_tokens_free(&p);
    *out = so;
    return 0;
}

void sf_sysone_close(sf_sysone *so) { free(so); }

int sf_sysone_symbol_token(const sf_sysone *so, sf_sysone_type type, int i) {
    return so->symbol[type == SF_SYSONE_SCORE ? 26 + i : i];
}

void sf_sysone_state_prefix(sf_sysone *so, const char *state, ds4_tokens *out) {
    ds4_chat_begin(so->e, out);
    ds4_chat_append_message(so->e, out, "system", SYS);
    ds4_tokens_push(out, ds4_token_user(so->e));
    ds4_tokenize_text(so->e, "State:\n", out);
    ds4_tokenize_text(so->e, state, out);
}

/* "X. name: text\n" for option i; caller frees. */
static char *option_line(const sf_sysone_question *q, int i) {
    const char *text = q->option_texts ? q->option_texts[i] : NULL;
    int has_text = text && text[0];
    const char *label = q->type == SF_SYSONE_CHOICE ? q->option_names[i]
                      : q->type == SF_SYSONE_NOUL ? (i == 0 ? "Yes" : "No") : NULL;
    char sym = q->type == SF_SYSONE_SCORE ? (char)('0' + i) : (char)('A' + i);
    size_t n = (label ? strlen(label) : 0) + (text ? strlen(text) : 0) + 16;
    char *line = malloc(n);
    if (label && has_text) snprintf(line, n, "%c. %s: %s\n", sym, label, text);
    else if (label) snprintf(line, n, "%c. %s\n", sym, label);
    else snprintf(line, n, "%c. %s\n", sym, text ? text : "");
    return line;
}

void sf_sysone_question_suffix(sf_sysone *so, const sf_sysone_question *q, ds4_tokens *out) {
    ds4_tokenize_text(so->e, "\n\nQuestion: ", out);
    ds4_tokenize_text(so->e, q->instructions, out);
    ds4_tokenize_text(so->e, "\nOptions:\n", out);
    for (int i = 0; i < q->n_options; i++) {
        char *line = option_line(q, i);
        ds4_tokenize_text(so->e, line, out);
        free(line);
    }
    ds4_tokenize_text(so->e, "Answer with the identifier only.", out);
    ds4_chat_append_assistant_prefix(so->e, out, DS4_THINK_NONE);
    if (ANSWER_PREFILL[0]) ds4_tokenize_text(so->e, ANSWER_PREFILL, out);
}

char *sf_sysone_turn_text(const sf_sysone_question *q) {
    size_t cap = strlen(q->instructions) + 160, len = 0;
    char *out = malloc(cap);
    len = (size_t)snprintf(out, cap, "Question about the conversation above: %s\nOptions:\n", q->instructions);
    for (int i = 0; i <= q->n_options; i++) {
        char *line = i < q->n_options ? option_line(q, i) : NULL;
        const char *piece = line ? line : "Answer with the identifier only.";
        size_t n = strlen(piece);
        if (len + n + 1 > cap) { cap = (len + n + 1) * 2; out = realloc(out, cap); }
        memcpy(out + len, piece, n + 1);
        len += n;
        free(line);
    }
    return out;
}

void sf_sysone_finish(sf_sysone_type type, double temperature, sf_sysone_answer *a) {
    const int n = a->n_options;
    if (temperature <= 0) temperature = 1.0;
    double mx = -INFINITY, sum = 0;
    for (int i = 0; i < n; i++) if (a->logit[i] / temperature > mx) mx = a->logit[i] / temperature;
    for (int i = 0; i < n; i++) sum += a->p[i] = exp(a->logit[i] / temperature - mx);
    a->top = 0;
    for (int i = 0; i < n; i++) {
        a->p[i] /= sum;
        if (a->p[i] > a->p[a->top]) a->top = i;
    }
    a->unstable = 0;
    if (n > 1) {
        double second = -INFINITY;
        for (int i = 0; i < n; i++) if (i != a->top && a->logit[i] > second) second = a->logit[i];
        a->unstable = (double)a->logit[a->top] - second < SF_SYSONE_DELTA95;
    }
    if (type == SF_SYSONE_NOUL) {
        a->value = a->p[0];
        a->confidence = fabs(2 * a->p[0] - 1);
    } else if (type == SF_SYSONE_CHOICE) {
        a->value = a->p[a->top];
        a->confidence = n == 1 ? 1.0 : (a->p[a->top] - 1.0 / n) / (1.0 - 1.0 / n);
    } else {
        double mad = 0, spread = 0, value = 0;
        for (int i = 0; i < n; i++) {
            mad += fabs(i - (n - 1) / 2.0) / n;
            spread += a->p[i] * fabs((double)(i - a->top));
            value += i * a->p[i];
        }
        a->value = value;
        a->confidence = n == 1 ? 1.0 : fmax(0.0, 1.0 - spread / mad);
    }
}

static int question_valid(const sf_sysone_question *q, int k, char *err, size_t errlen) {
    int max = q->type == SF_SYSONE_SCORE ? 10 : SF_SYSONE_MAX_OPTIONS;
    if (!q->instructions || q->n_options < 1 || q->n_options > max ||
        (q->type == SF_SYSONE_NOUL && q->n_options != 2) ||
        (q->type == SF_SYSONE_CHOICE && !q->option_names) ||
        (q->type == SF_SYSONE_SCORE && !q->option_texts)) {
        snprintf(err, errlen, "question %d: invalid shape (type %d, %d options)", k, q->type, q->n_options);
        return 0;
    }
    return 1;
}

int sf_sysone_answer_from(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                          const ds4_session_snapshot *snap,
                          const sf_sysone_question *q, int n_questions,
                          const double *temperature, sf_sysone_answer *answers,
                          char *err, size_t errlen) {
    return sf_sysone_answer_suffixes(so, s, prefix, snap, q, n_questions, NULL,
                                     temperature, answers, err, errlen);
}

int sf_sysone_answer_suffixes(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                              const ds4_session_snapshot *snap,
                              const sf_sysone_question *q, int n_questions,
                              const ds4_tokens *suffixes,
                              const double *temperature, sf_sysone_answer *answers,
                              char *err, size_t errlen) {
    if (ds4_session_steering(s)) { snprintf(err, errlen, "system one needs an unsteered session"); return 1; }
    for (int k = 0; k < n_questions; k++) if (!question_valid(&q[k], k, err, errlen)) return 1;

    ds4_tokens full = {0};
    ds4_session_snapshot own = {0};
    int rc = 1, dirty = 0, logged_sweep = 0;
    if (!snap && n_questions > 1) {
        if (ds4_session_save_snapshot(s, &own, err, errlen) != 0) goto done;
        snap = &own;
    }

    for (int k = 0; k < n_questions; k++) {
        sf_sysone_answer *a = &answers[k];
        memset(a, 0, sizeof(*a));
        a->n_options = q[k].n_options;
        const double t0 = now_ms();
        double t = temperature ? temperature[k] : 1.0;
        if (q[k].n_options == 1) { /* answered without touching the session */
            sf_sysone_finish(q[k].type, t, a);
            a->legal_mass = 1.0;
            continue;
        }
        if (dirty) {
            if (ds4_session_load_snapshot(s, snap, err, errlen) != 0) goto done;
            if (ds4_session_pos(s) != prefix->len || !ds4_session_checkpoint_valid(s)) {
                snprintf(err, errlen, "snapshot restore left pos %d (want %d), checkpoint %s",
                         ds4_session_pos(s), prefix->len, ds4_session_checkpoint_valid(s) ? "valid" : "invalid");
                goto done;
            }
        }
        full.len = 0;
        ds4_tokens_copy(&full, prefix);
        if (suffixes) for (int i = 0; i < suffixes[k].len; i++) ds4_tokens_push(&full, suffixes[k].v[i]);
        else sf_sysone_question_suffix(so, &q[k], &full);
        a->suffix_tokens = full.len - prefix->len;
        if (full.len >= ds4_session_ctx(s)) { snprintf(err, errlen, "max_tokens_exceeded"); goto done; }
        if (a->suffix_tokens >= 256 && !logged_sweep) {
            fprintf(stderr, "sysone: question suffix of %d tokens runs as a prefill sweep (slow)\n", a->suffix_tokens);
            logged_sweep = 1;
        }
        if (ds4_session_sync(s, &full, err, errlen) != 0) goto done;
        dirty = 1;
        for (int i = 0; i < a->n_options; i++) {
            ds4_token_score sc;
            if (!ds4_session_token_logprob(s, sf_sysone_symbol_token(so, q[k].type, i), &sc)) {
                snprintf(err, errlen, "question %d: no logits", k);
                goto done;
            }
            a->logit[i] = sc.logit;
            a->legal_mass += exp((double)sc.logprob);
        }
        sf_sysone_finish(q[k].type, t, a);
        a->ms = now_ms() - t0;
    }
    rc = 0;
done:
    ds4_session_snapshot_free(&own);
    ds4_tokens_free(&full);
    return rc;
}

int sf_sysone_decide(sf_sysone *so, ds4_session *s, const char *state,
                     const sf_sysone_question *q, int n_questions,
                     const double *temperature, sf_sysone_answer *answers,
                     int *prefix_tokens, char *err, size_t errlen) {
    if (ds4_session_steering(s)) { snprintf(err, errlen, "system one needs an unsteered session"); return 1; }
    for (int k = 0; k < n_questions; k++) if (!question_valid(&q[k], k, err, errlen)) return 1;
    ds4_tokens prefix = {0};
    int rc = 1;
    sf_sysone_state_prefix(so, state, &prefix);
    if (prefix_tokens) *prefix_tokens = prefix.len;
    if (prefix.len >= ds4_session_ctx(s)) snprintf(err, errlen, "max_tokens_exceeded");
    else if (ds4_session_sync(s, &prefix, err, errlen) == 0)
        rc = sf_sysone_answer_from(so, s, &prefix, NULL, q, n_questions, temperature, answers, err, errlen);
    ds4_tokens_free(&prefix);
    return rc;
}
