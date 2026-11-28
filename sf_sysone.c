/* System One readout (change 800). Only ds4.h and libc: the engine sources
 * stay untouched, so upstream syncs never conflict here. */
#include "sf_sysone.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Template versions 1 and 2 (docs/system-one.md, "Template"); they differ only in the question suffix. */
static const char SYS[] =
    "You are a decision function. Read the state and answer the question by "
    "choosing exactly one of the listed options.";
/* Probe winner T-C: no answer prefill, the symbol is read right after </think>. */
static const char ANSWER_PREFILL[] = "";

#define N_SYMBOLS 36 /* A-Z then 0-9 */

struct sf_sysone {
    ds4_engine *e;
    int template_version;
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

int sf_sysone_open(sf_sysone **out, ds4_engine *e, int template_version, char *err, size_t errlen) {
    *out = NULL;
    if (template_version != 1 && template_version != 2) {
        snprintf(err, errlen, "unknown template version %d", template_version);
        return 1;
    }
    sf_sysone *so = calloc(1, sizeof(*so));
    if (!so) { snprintf(err, errlen, "out of memory"); return 1; }
    so->e = e;
    so->template_version = template_version;
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

int sf_sysone_template(const sf_sysone *so) { return so->template_version; }

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

static int is_big(const sf_sysone_question *q) {
    return q->type == SF_SYSONE_CHOICE && q->n_options > SF_SYSONE_MAX_OPTIONS;
}

/* a040: a choice above 26 options numbers its lines "[k] " and the answer opens with "[". */
static const char BIG_PREFILL[] = "[";

/* "X. name: text\n" for option i ("[k] name: text\n" for a big choice); caller frees. */
static char *option_line(const sf_sysone_question *q, int i) {
    const char *text = q->option_texts ? q->option_texts[i] : NULL;
    int has_text = text && text[0];
    const char *label = q->type == SF_SYSONE_CHOICE ? q->option_names[i]
                      : q->type == SF_SYSONE_NOUL ? (i == 0 ? "Yes" : "No") : NULL;
    char sym[8];
    if (is_big(q)) snprintf(sym, sizeof(sym), "[%d]", i);
    else snprintf(sym, sizeof(sym), "%c.", q->type == SF_SYSONE_SCORE ? (char)('0' + i) : (char)('A' + i));
    size_t n = (label ? strlen(label) : 0) + (text ? strlen(text) : 0) + 16;
    char *line = malloc(n);
    if (label && has_text) snprintf(line, n, "%s %s: %s\n", sym, label, text);
    else if (label) snprintf(line, n, "%s %s\n", sym, label);
    else snprintf(line, n, "%s %s\n", sym, text ? text : "");
    return line;
}

static void text_add(char **buf, size_t *len, size_t *cap, const char *s) {
    size_t n = strlen(s);
    if (*len + n + 1 > *cap) {
        *cap = (*len + n + 1) * 2;
        *buf = realloc(*buf, *cap);
    }
    memcpy(*buf + *len, s, n + 1);
    *len += n;
}

void sf_sysone_question_suffix(sf_sysone *so, const sf_sysone_question *q, ds4_tokens *out) {
    /* a000: no "Options:" header, the suffix tokenized as one string. a040: big choices exist only in this shape. */
    if (so->template_version == 2 || is_big(q)) {
        char *text = NULL;
        size_t len = 0, cap = 0;
        text_add(&text, &len, &cap, "\n\nQuestion: ");
        text_add(&text, &len, &cap, q->instructions);
        text_add(&text, &len, &cap, "\n");
        for (int i = 0; i < q->n_options; i++) {
            char *line = option_line(q, i);
            text_add(&text, &len, &cap, line);
            free(line);
        }
        text_add(&text, &len, &cap, "Answer with the identifier only.");
        ds4_tokenize_text(so->e, text, out);
        free(text);
        ds4_chat_append_assistant_prefix(so->e, out, DS4_THINK_NONE);
        if (is_big(q)) ds4_tokenize_text(so->e, BIG_PREFILL, out);
        else if (ANSWER_PREFILL[0]) ds4_tokenize_text(so->e, ANSWER_PREFILL, out);
        return;
    }
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
    int max = q->type == SF_SYSONE_SCORE ? 10 : q->type == SF_SYSONE_CHOICE ? SF_SYSONE_MAX_CHOICE : 2;
    if (!q->instructions || q->n_options < 1 || q->n_options > max ||
        (q->type == SF_SYSONE_NOUL && q->n_options != 2) ||
        (q->type == SF_SYSONE_CHOICE && !q->option_names) ||
        (q->type == SF_SYSONE_SCORE && !q->option_texts)) {
        snprintf(err, errlen, "question %d: invalid shape (type %d, %d options)", k, q->type, q->n_options);
        return 0;
    }
    return 1;
}

/* ---- a040: trie readout ---- */

typedef struct {
    const int *paths; const int *lens;
    sf_sysone_trie_read read; void *ud;
    float *logp; int evaluated;
    char *err; size_t errlen;
} trie_ctx;

static int trie_node(trie_ctx *c, const int *prefix, int depth, const int *members, int nm, double pathp,
                     double *mass_out) {
    int tok[SF_SYSONE_MAX_CHOICE], nt = 0;
    double prob[SF_SYSONE_MAX_CHOICE];
    for (int i = 0; i < nm; i++) {
        int t = c->paths[members[i] * SF_SYSONE_TRIE_DEPTH + depth], seen = 0;
        for (int j = 0; j < nt && !seen; j++) seen = tok[j] == t;
        if (!seen) tok[nt++] = t;
    }
    if (c->read(c->ud, prefix, depth, tok, nt, prob) != 0) return 1;
    c->evaluated++;
    double m = 0;
    for (int j = 0; j < nt; j++) m += prob[j];
    if (mass_out) *mass_out = m;
    if (!(m > 0)) { snprintf(c->err, c->errlen, "trie node at depth %d has no probability mass", depth); return 1; }
    int sub[SF_SYSONE_MAX_CHOICE], next[SF_SYSONE_TRIE_DEPTH];
    if (depth) memcpy(next, prefix, sizeof(int) * (size_t)depth);
    for (int j = 0; j < nt; j++) {
        int ns = 0;
        for (int i = 0; i < nm; i++)
            if (c->paths[members[i] * SF_SYSONE_TRIE_DEPTH + depth] == tok[j]) sub[ns++] = members[i];
        const double p = pathp * prob[j] / m;
        if (ns == 1) { c->logp[sub[0]] = (float)log(p); continue; }  /* one continuation: conditional 1 */
        if (p < 1e-4) {                                                /* not expanded: equal shares */
            for (int i = 0; i < ns; i++) c->logp[sub[i]] = (float)log(p / ns);
            continue;
        }
        next[depth] = tok[j];
        if (trie_node(c, next, depth + 1, sub, ns, p, NULL) != 0) return 1;
    }
    return 0;
}

int sf_sysone_trie_probs(const int *paths, const int *lens, int n, sf_sysone_trie_read read, void *ud,
                         float *logp, double *legal_mass, int *evaluated, char *err, size_t errlen) {
    if (n < 1 || n > SF_SYSONE_MAX_CHOICE) { snprintf(err, errlen, "trie: %d options", n); return 1; }
    for (int k = 0; k < n; k++) {
        if (lens[k] < 1 || lens[k] > SF_SYSONE_TRIE_DEPTH) {
            snprintf(err, errlen, "option %d: id path of %d tokens", k, lens[k]);
            return 1;
        }
        for (int j = 0; j < n; j++) {
            if (j == k || lens[j] < lens[k]) continue;
            if (!memcmp(&paths[k * SF_SYSONE_TRIE_DEPTH], &paths[j * SF_SYSONE_TRIE_DEPTH], sizeof(int) * (size_t)lens[k])) {
                snprintf(err, errlen, "option %d: id path is a prefix of option %d's", k, j);
                return 1;
            }
        }
    }
    int members[SF_SYSONE_MAX_CHOICE];
    for (int k = 0; k < n; k++) members[k] = k;
    trie_ctx c = {paths, lens, read, ud, logp, 0, err, errlen};
    int rc = trie_node(&c, NULL, 0, members, n, 1.0, legal_mass);
    *evaluated = c.evaluated;
    return rc;
}

/* The session is at the root (prefix + big suffix); nodes below it are reached
 * from a snapshot of the root, saved on first need. */
typedef struct {
    sf_sysone *so; ds4_session *s; ds4_session_snapshot root; int saved;
    char *err; size_t errlen;
} trie_session;

static int trie_read_session(void *ud, const int *path, int depth, const int *tokens, int n, double *prob) {
    trie_session *t = ud;
    if (depth > 0) {
        if (!t->saved) {
            if (ds4_session_save_snapshot(t->s, &t->root, t->err, t->errlen) != 0) return 1;
            t->saved = 1;
        } else if (ds4_session_load_snapshot(t->s, &t->root, t->err, t->errlen) != 0) return 1;
        for (int i = 0; i < depth; i++)
            if (ds4_session_eval(t->s, path[i], t->err, t->errlen) != 0) return 1;
    }
    for (int i = 0; i < n; i++) {
        ds4_token_score sc;
        if (!ds4_session_token_logprob(t->s, tokens[i], &sc)) { snprintf(t->err, t->errlen, "no logits"); return 1; }
        prob[i] = exp((double)sc.logprob);
    }
    return 0;
}

/* Token paths of "k]" after BIG_PREFILL, k = 0..n-1. */
static int big_paths(sf_sysone *so, int n, int *paths, int *lens, char *err, size_t errlen) {
    ds4_tokens head = {0}, f = {0};
    ds4_tokenize_text(so->e, BIG_PREFILL, &head);
    int rc = 0;
    for (int k = 0; k < n && !rc; k++) {
        char txt[16];
        snprintf(txt, sizeof(txt), "%s%d]", BIG_PREFILL, k);
        f.len = 0;
        ds4_tokenize_text(so->e, txt, &f);
        lens[k] = f.len - head.len;
        if (!ds4_tokens_starts_with(&f, &head) || lens[k] < 1 || lens[k] > SF_SYSONE_TRIE_DEPTH) {
            snprintf(err, errlen, "option %d: \"%s\" does not tokenize as \"%s\" plus an id path", k, txt, BIG_PREFILL);
            rc = 1;
        } else memcpy(&paths[k * SF_SYSONE_TRIE_DEPTH], &f.v[head.len], sizeof(int) * (size_t)lens[k]);
    }
    ds4_tokens_free(&head);
    ds4_tokens_free(&f);
    return rc;
}

int sf_sysone_answer_from(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                          const ds4_session_snapshot *snap,
                          const sf_sysone_question *q, int n_questions,
                          const double *temperature, sf_sysone_answer *answers,
                          char *err, size_t errlen, sf_sysone_timing *timing) {
    return sf_sysone_answer_suffixes(so, s, prefix, snap, q, n_questions, NULL,
                                     temperature, answers, err, errlen, timing);
}

int sf_sysone_answer_suffixes(sf_sysone *so, ds4_session *s, const ds4_tokens *prefix,
                              const ds4_session_snapshot *snap,
                              const sf_sysone_question *q, int n_questions,
                              const ds4_tokens *suffixes,
                              const double *temperature, sf_sysone_answer *answers,
                              char *err, size_t errlen, sf_sysone_timing *timing) {
    if (ds4_session_steering(s)) { snprintf(err, errlen, "system one needs an unsteered session"); return 1; }
    for (int k = 0; k < n_questions; k++) {
        if (!question_valid(&q[k], k, err, errlen)) return 1;
        if (suffixes && is_big(&q[k])) {
            snprintf(err, errlen, "question %d: more than 26 options is not supported on a live state", k);
            return 1;
        }
    }

    ds4_tokens full = {0};
    ds4_session_snapshot own = {0};
    int rc = 1, dirty = 0, logged_sweep = 0;
    if (timing) timing->save_ms = 0;
    if (!snap && n_questions > 1) {
        const double ts = now_ms();
        if (ds4_session_save_snapshot(s, &own, err, errlen) != 0) goto done;
        if (timing) timing->save_ms = now_ms() - ts;
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
            const double tr = now_ms();
            if (ds4_session_load_snapshot(s, snap, err, errlen) != 0) goto done;
            if (ds4_session_pos(s) != prefix->len || !ds4_session_checkpoint_valid(s)) {
                snprintf(err, errlen, "snapshot restore left pos %d (want %d), checkpoint %s",
                         ds4_session_pos(s), prefix->len, ds4_session_checkpoint_valid(s) ? "valid" : "invalid");
                goto done;
            }
            a->restore_ms = now_ms() - tr;
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
        const double te = now_ms();
        if (ds4_session_sync(s, &full, err, errlen) != 0) goto done;
        a->eval_ms = now_ms() - te;
        dirty = 1;
        if (is_big(&q[k])) {
            int paths[SF_SYSONE_MAX_CHOICE * SF_SYSONE_TRIE_DEPTH], lens[SF_SYSONE_MAX_CHOICE];
            trie_session ts = {so, s, {0}, 0, err, errlen};
            int trc = big_paths(so, q[k].n_options, paths, lens, err, errlen);
            if (!trc) trc = sf_sysone_trie_probs(paths, lens, q[k].n_options, trie_read_session, &ts,
                                                 a->logit, &a->legal_mass, &a->evaluated_nodes, err, errlen);
            ds4_session_snapshot_free(&ts.root);
            if (trc) goto done;
            sf_sysone_finish(q[k].type, t, a);
            a->ms = now_ms() - t0;
            continue;
        }
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
                     int *prefix_tokens, char *err, size_t errlen, sf_sysone_timing *timing) {
    if (ds4_session_steering(s)) { snprintf(err, errlen, "system one needs an unsteered session"); return 1; }
    for (int k = 0; k < n_questions; k++) if (!question_valid(&q[k], k, err, errlen)) return 1;
    ds4_tokens prefix = {0};
    int rc = 1;
    sf_sysone_state_prefix(so, state, &prefix);
    if (prefix_tokens) *prefix_tokens = prefix.len;
    if (timing) *timing = (sf_sysone_timing){0};
    const double tp = now_ms();
    if (prefix.len >= ds4_session_ctx(s)) snprintf(err, errlen, "max_tokens_exceeded");
    else if (ds4_session_sync(s, &prefix, err, errlen) == 0) {
        if (timing) timing->prefill_ms = now_ms() - tp;
        rc = sf_sysone_answer_from(so, s, &prefix, NULL, q, n_questions, temperature, answers, err, errlen, timing);
    }
    ds4_tokens_free(&prefix);
    return rc;
}
