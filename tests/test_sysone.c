/* System One readout tests (change 800).
 *   ./tests/test_sysone                    model-less math checks (make test)
 *   ./tests/test_sysone MODEL              model-backed checks (make test-sysone)
 *   ./tests/test_sysone MODEL --tokens     token dump of fixture 1
 *   ./tests/test_sysone MODEL --probe      template probe T-A/T-B/T-C
 *   ./tests/test_sysone MODEL --special-text  special-token text in a state stays text (a005)
 *   ./tests/test_sysone MODEL --timing     phase timings of a decision (a080)
 * Every check prints a line naming it: an exit code alone proves nothing. */
#include "sf_sysone.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int failures;

static void check(int ok, const char *name) {
    printf("sysone: %s %s\n", name, ok ? "OK" : "FAIL");
    if (!ok) failures++;
}

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

/* ---- model-less ---- */

static void set_p(sf_sysone_answer *a, int n, const double *p) {
    memset(a, 0, sizeof(*a));
    a->n_options = n;
    for (int i = 0; i < n; i++) a->logit[i] = p[i] > 0 ? (float)log(p[i]) : -1e30f;
}

static int math_checks(void) {
    {   /* 835: the live turn text */
        static const char *const names[] = {"x", "y"};
        sf_sysone_question q = {SF_SYSONE_CHOICE, "Pick one.", 2, names, NULL};
        char *t = sf_sysone_turn_text(&q);
        const char *tail = "A. x\nB. y\nAnswer with the identifier only.";
        check(!strncmp(t, "Question about the conversation above: Pick one.\nOptions:\n", 58) &&
              strlen(t) >= strlen(tail) && !strcmp(t + strlen(t) - strlen(tail), tail), "turn text layout");
        free(t);
    }
    sf_sysone_answer a;
    set_p(&a, 3, (double[]){0, 0.57, 0.43});
    sf_sysone_finish(SF_SYSONE_SCORE, 1.0, &a);
    check(fabs(a.confidence - 0.35) <= 0.01 && a.top == 1, "finish score example 0.35");

    set_p(&a, 3, (double[]){0.92, 0.05, 0.03});
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    check(fabs(a.confidence - 0.88) <= 0.005 && a.top == 0, "finish choice example 0.88");

    set_p(&a, 1, (double[]){1});
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    check(a.confidence == 1.0 && a.p[0] == 1.0, "finish one option");
    sf_sysone_finish(SF_SYSONE_SCORE, 1.0, &a);
    check(a.confidence == 1.0, "finish one level");

    memset(&a, 0, sizeof(a));
    a.n_options = 4;
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    check(fabs(a.confidence) < 1e-12 && a.top == 0, "finish equal logits confidence 0");

    set_p(&a, 3, (double[]){0.7, 0.2, 0.1});
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    double p1 = a.p[0];
    sf_sysone_finish(SF_SYSONE_CHOICE, 2.0, &a);
    check(a.p[0] < p1 && a.top == 0, "finish temperature 2 flattens, keeps top");

    set_p(&a, 2, (double[]){0.8, 0.2});
    sf_sysone_finish(SF_SYSONE_NOUL, 1.0, &a);
    check(fabs(a.value - 0.8) < 1e-6 && fabs(a.confidence - 0.6) < 1e-6, "finish noul value and confidence");

    set_p(&a, 5, (double[]){0.1, 0.1, 0.2, 0.3, 0.3});
    sf_sysone_finish(SF_SYSONE_SCORE, 1.0, &a);
    check(fabs(a.value - 2.6) < 1e-6 && a.top == 3, "finish score value, tie to lowest index");

    memset(&a, 0, sizeof(a));
    a.n_options = 3;
    a.logit[0] = 10.0f; a.logit[1] = 10.0f - (float)(SF_SYSONE_DELTA95 / 2); a.logit[2] = 0.0f;
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    int close_gap = a.unstable;
    a.logit[1] = 10.0f - (float)(SF_SYSONE_DELTA95 * 2);
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    check(close_gap && !a.unstable && SF_SYSONE_DELTA95 > 0, "finish unstable below SF_SYSONE_DELTA95 only");
    set_p(&a, 1, (double[]){1});
    sf_sysone_finish(SF_SYSONE_CHOICE, 1.0, &a);
    check(!a.unstable, "finish one option is never unstable");
    return failures ? 1 : 0;
}

/* ---- fixtures ---- */

typedef enum { EXPECT_TOP, EXPECT_BELOW, EXPECT_ABOVE, EXPECT_TOP_LE, EXPECT_TOP_GE } expect_kind;

typedef struct {
    const char *state;
    sf_sysone_question q;
    expect_kind kind;
    int arg; /* option index, or score bound */
} fixture;

static const char *const EN_TICKET[] = {"refund_request", "shipping_question", "praise"};
static const char *const EN_SENT[] = {"very negative", "negative", "neutral", "positive", "very positive"};
static const char *const EN_OPS[] = {"ignore", "monitor", "page_oncall"};
static const char *const IT_TICKET[] = {"richiesta_rimborso", "domanda_spedizione", "complimento"};
static const char *const IT_SENT[] = {"molto negativo", "negativo", "neutro", "positivo", "molto positivo"};
static const char *const IT_LOGIN[] = {"problema_accesso", "fatturazione", "altro"};
static const char *const IT_SUB[] = {"disdetta", "upgrade", "reclamo"};
static const char *const NO_TEXT[] = {NULL, NULL};

#define CHOICE(names) {SF_SYSONE_CHOICE, "Classify the message.", 3, names, NULL}
#define NOUL(stmt) {SF_SYSONE_NOUL, stmt, 2, NULL, NO_TEXT}
#define SCORE(levels) {SF_SYSONE_SCORE, "Rate the sentiment of the message.", 5, NULL, levels}

static const char S1[] = "My package arrived broken and I want my money back.";
static const char S7[] = "Il pacco è arrivato rotto e voglio il rimborso.";

static const fixture FIX[12] = {
    {S1, CHOICE(EN_TICKET), EXPECT_TOP, 0},
    {S1, NOUL("The customer is satisfied."), EXPECT_BELOW, 0},
    {S1, SCORE(EN_SENT), EXPECT_TOP_LE, 1},
    {"Meeting moved to Thursday 3pm, room B.", NOUL("The meeting is on Thursday."), EXPECT_ABOVE, 0},
    {"Server CPU at 97% for 20 minutes, three alerts fired.", CHOICE(EN_OPS), EXPECT_TOP, 2},
    {"The invoice total is 1,250 EUR, due on the 30th.", NOUL("The invoice is overdue."), EXPECT_BELOW, 0},
    {S7, CHOICE(IT_TICKET), EXPECT_TOP, 0},
    {S7, NOUL("Il cliente è soddisfatto."), EXPECT_BELOW, 0},
    {"Grazie mille, servizio perfetto e consegna in anticipo!", SCORE(IT_SENT), EXPECT_TOP_GE, 3},
    {"La riunione è spostata a giovedì alle 15.", NOUL("La riunione è di giovedì."), EXPECT_ABOVE, 0},
    {"Ho dimenticato la password e non riesco ad accedere.", CHOICE(IT_LOGIN), EXPECT_TOP, 0},
    {"Vorrei disdire l'abbonamento da fine mese.", CHOICE(IT_SUB), EXPECT_TOP, 0},
};

static int fixture_ok(const fixture *f, const sf_sysone_answer *a) {
    switch (f->kind) {
    case EXPECT_TOP: return a->top == f->arg;
    case EXPECT_BELOW: return a->value < 0.5;
    case EXPECT_ABOVE: return a->value > 0.5;
    case EXPECT_TOP_LE: return a->top <= f->arg;
    case EXPECT_TOP_GE: return a->top >= f->arg;
    }
    return 0;
}

/* ---- engine ---- */

static ds4_engine *engine;
static ds4_session *session;
static sf_sysone *so;

static int open_all(const char *model) {
    char err[1024] = {0};
    ds4_engine_options opt = {.model_path = model, .backend = DS4_BACKEND_METAL,
        .context_size = 4096, .power_percent = 100, .ssd_streaming = true,
        .ssd_streaming_cache_bytes = UINT64_C(32) << 30};
    if (ds4_engine_open(&engine, &opt) != 0) { fprintf(stderr, "engine open failed\n"); return 0; }
    if (ds4_session_create(&session, engine, opt.context_size) != 0) { fprintf(stderr, "session failed\n"); return 0; }
    int rc = sf_sysone_open(&so, engine, SF_SYSONE_TEMPLATE_VERSION, err, sizeof(err));
    if (rc) fprintf(stderr, "%s\n", err);
    check(rc == 0, "symbols A-Z 0-9 single tokens after the prefill");
    return rc == 0;
}

static void close_all(void) {
    sf_sysone_close(so);
    if (session) ds4_session_free(session);
    if (engine) ds4_engine_close(engine);
}

static void print_tokens(const char *label, const ds4_tokens *t, int from) {
    printf("%s (%d tokens):", label, t->len - from);
    for (int i = from; i < t->len; i++) {
        size_t n = 0;
        char *txt = ds4_token_text(engine, t->v[i], &n);
        printf(" %d'%.*s'", t->v[i], (int)n, txt ? txt : "");
        free(txt);
    }
    printf("\n");
}

static int mode_tokens(void) {
    ds4_tokens prefix = {0}, full = {0};
    sf_sysone_state_prefix(so, FIX[0].state, &prefix);
    ds4_tokens_copy(&full, &prefix);
    sf_sysone_question_suffix(so, &FIX[0].q, &full);
    print_tokens("prefix", &prefix, 0);
    print_tokens("suffix", &full, prefix.len);
    check(ds4_tokens_starts_with(&full, &prefix), "tokens prefix is a token prefix of prefix+suffix");
    ds4_tokens_free(&prefix);
    ds4_tokens_free(&full);
    return failures ? 1 : 0;
}

/* Template probe: the candidates live here, not in the module. */
typedef struct {
    const char *id, *prefill, *option_fmt, *instruction;
} candidate;

static const candidate CAND[3] = {
    {"T-A", "Best answer: [", "[%c] %s\n", "Select one option. Answer only with its bracketed identifier."},
    {"T-B", "[", "[%c] %s\n", "Select one option. Answer only with its bracketed identifier."},
    {"T-C", "", "%c. %s\n", "Answer with the identifier only."},
};

static void probe_suffix(const candidate *c, const sf_sysone_question *q, ds4_tokens *out) {
    char line[512];
    ds4_tokenize_text(engine, "\n\nQuestion: ", out);
    ds4_tokenize_text(engine, q->instructions, out);
    ds4_tokenize_text(engine, "\nOptions:\n", out);
    for (int i = 0; i < q->n_options; i++) {
        const char *text = q->option_texts ? q->option_texts[i] : NULL;
        const char *label = q->type == SF_SYSONE_CHOICE ? q->option_names[i]
                          : q->type == SF_SYSONE_NOUL ? (i == 0 ? "Yes" : "No") : NULL;
        char body[400];
        if (label && text && text[0]) snprintf(body, sizeof(body), "%s: %s", label, text);
        else snprintf(body, sizeof(body), "%s", label ? label : (text ? text : ""));
        snprintf(line, sizeof(line), c->option_fmt,
                 q->type == SF_SYSONE_SCORE ? '0' + i : 'A' + i, body);
        ds4_tokenize_text(engine, line, out);
    }
    ds4_tokenize_text(engine, c->instruction, out);
    ds4_chat_append_assistant_prefix(engine, out, DS4_THINK_NONE);
    if (c->prefill[0]) ds4_tokenize_text(engine, c->prefill, out);
}

static int mode_probe(void) {
    char err[1024] = {0};
    double mass_sum[3] = {0}, mass_min[3] = {1, 1, 1};
    int correct[3] = {0};
    for (int f = 0; f < 12; f++) {
        ds4_tokens prefix = {0}, full = {0};
        ds4_session_snapshot snap = {0};
        sf_sysone_state_prefix(so, FIX[f].state, &prefix);
        if (ds4_session_sync(session, &prefix, err, sizeof(err)) != 0 ||
            ds4_session_save_snapshot(session, &snap, err, sizeof(err)) != 0) {
            fprintf(stderr, "probe: %s\n", err);
            return 1;
        }
        for (int c = 0; c < 3; c++) {
            if (c && ds4_session_load_snapshot(session, &snap, err, sizeof(err)) != 0) {
                fprintf(stderr, "probe: %s\n", err);
                return 1;
            }
            ds4_tokens_copy(&full, &prefix);
            probe_suffix(&CAND[c], &FIX[f].q, &full);
            if (ds4_session_sync(session, &full, err, sizeof(err)) != 0) { fprintf(stderr, "probe: %s\n", err); return 1; }
            sf_sysone_answer a = {.n_options = FIX[f].q.n_options};
            for (int i = 0; i < a.n_options; i++) {
                ds4_token_score sc;
                ds4_session_token_logprob(session, sf_sysone_symbol_token(so, FIX[f].q.type, i), &sc);
                a.logit[i] = sc.logit;
                a.legal_mass += exp((double)sc.logprob);
            }
            sf_sysone_finish(FIX[f].q.type, 1.0, &a);
            int ok = fixture_ok(&FIX[f], &a);
            correct[c] += ok;
            mass_sum[c] += a.legal_mass;
            if (a.legal_mass < mass_min[c]) mass_min[c] = a.legal_mass;
            printf("probe %s fixture %2d top %d value %.3f mass %.4f %s\n", CAND[c].id, f + 1,
                   a.top, a.value, a.legal_mass, ok ? "ok" : "WRONG");
        }
        ds4_session_snapshot_free(&snap);
        ds4_tokens_free(&prefix);
        ds4_tokens_free(&full);
    }
    printf("\n| Id | Prefill | Correct | Mean legal mass | Min legal mass |\n|---|---|---|---|---|\n");
    for (int c = 0; c < 3; c++)
        printf("| %s | `%s` | %d/12 | %.4f | %.4f |\n", CAND[c].id, CAND[c].prefill, correct[c],
               mass_sum[c] / 12, mass_min[c]);
    return 0;
}

/* a005: special-token text inside a state must stay plain text. Each id is
 * counted in the prefix of a plain state (the template's own count) and of a
 * state that carries the token's text. */
static int count_id(const ds4_tokens *t, int id) {
    int n = 0;
    for (int i = 0; i < t->len; i++) n += t->v[i] == id;
    return n;
}

static int mode_special_text(void) {
    ds4_tokens bos = {0}, sys = {0}, asst = {0}, think = {0};
    ds4_chat_begin(engine, &bos);
    ds4_chat_append_message(engine, &sys, "system", "");
    ds4_chat_append_assistant_prefix(engine, &asst, DS4_THINK_NONE);
    ds4_chat_append_assistant_prefix(engine, &think, DS4_THINK_HIGH);
    struct { const char *name; int id; } tok[6] = {
        {"BOS", bos.len ? bos.v[0] : -1}, {"System", sys.len ? sys.v[0] : -1},
        {"User", ds4_token_user(engine)}, {"Assistant", ds4_token_assistant(engine)},
        {"<think>", think.len > 1 ? think.v[think.len - 1] : -1},
        {"</think>", asst.len > 1 ? asst.v[asst.len - 1] : -1},
    };
    ds4_tokens plain = {0};
    sf_sysone_state_prefix(so, "hello world", &plain);
    for (int k = 0; k < 6; k++) {
        if (tok[k].id < 0) { check(0, tok[k].name); continue; }
        size_t n = 0;
        char *text = ds4_token_text(engine, tok[k].id, &n);
        char state[256];
        snprintf(state, sizeof(state), "hello %.*s world", (int)n, text ? text : "");
        ds4_tokens p = {0};
        sf_sysone_state_prefix(so, state, &p);
        int want = count_id(&plain, tok[k].id), got = count_id(&p, tok[k].id);
        char name[256];
        snprintf(name, sizeof(name), "special text %s (id %d, \"%.*s\") in the state: id %d times, template %d",
                 tok[k].name, tok[k].id, (int)n, text ? text : "", got, want);
        check(got == want, name);
        free(text);
        ds4_tokens_free(&p);
    }
    ds4_tokens_free(&plain);
    ds4_tokens_free(&bos);
    ds4_tokens_free(&sys);
    ds4_tokens_free(&asst);
    ds4_tokens_free(&think);
    return failures ? 1 : 0;
}

static int logits_equal(const sf_sysone_answer *a, const sf_sysone_answer *b) {
    return a->n_options == b->n_options && !memcmp(a->logit, b->logit, sizeof(float) * a->n_options);
}

static char *long_state(int bytes) {
    FILE *fp = fopen("speed-bench/promessi_sposi.txt", "rb");
    if (!fp) return NULL;
    char *buf = calloc(1, (size_t)bytes + 1);
    size_t n = fread(buf, 1, (size_t)bytes, fp);
    fclose(fp);
    while (n && (buf[n - 1] & 0xC0) == 0x80) n--; /* do not cut a UTF-8 sequence */
    if (n && (unsigned char)buf[n - 1] >= 0xC0) n--;
    buf[n] = 0;
    return buf;
}

static void timed(const char *label, const char *state, const sf_sysone_question *q, int n) {
    char err[1024] = {0};
    ds4_tokens prefix = {0};
    sf_sysone_answer a[3];
    int prefix_len = 0;
    sf_sysone_state_prefix(so, state, &prefix);
    double t0 = now_ms();
    int rc = ds4_session_sync(session, &prefix, err, sizeof(err));
    double t1 = now_ms();
    if (!rc) rc = sf_sysone_decide(so, session, state, q, n, NULL, a, &prefix_len, err, sizeof(err), NULL);
    double t2 = now_ms();
    if (rc) fprintf(stderr, "%s: %s\n", label, err);
    printf("sysone: timing %s: prefix %d tokens %.0f ms; %d questions (suffix %d/%d/%d tokens) %.0f ms\n",
           label, prefix_len, t1 - t0, n, a[0].suffix_tokens, n > 1 ? a[1].suffix_tokens : 0,
           n > 2 ? a[2].suffix_tokens : 0, t2 - t1);
    check(rc == 0, label);
    ds4_tokens_free(&prefix);
}

/* a080: phase timings of a decision. States: fixture 1 and the 655-token
 * promessi_sposi prefix; 1, 3 and 6 questions (fixtures 1-3 repeated); three
 * repetitions, each after a different short state so it starts unmatched. */
static int cmp_double(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static double median(double *v, int n) {
    qsort(v, (size_t)n, sizeof(*v), cmp_double);
    return n % 2 ? v[n / 2] : (v[n / 2 - 1] + v[n / 2]) / 2;
}

static int reset_session(int k, char *err, size_t errlen) {
    char text[64];
    ds4_tokens t = {0};
    snprintf(text, sizeof(text), "Reset number %d.", k);
    sf_sysone_state_prefix(so, text, &t);
    int rc = ds4_session_sync(session, &t, err, errlen);
    ds4_tokens_free(&t);
    return rc;
}

static int mode_timing(void) {
    char err[1024] = {0};
    char *big = long_state(2000);
    if (!big) { check(0, "timing: speed-bench/promessi_sposi.txt"); return 1; }
    const char *states[2] = {S1, big};
    const int counts[3] = {1, 3, 6};
    sf_sysone_question q[6];
    for (int k = 0; k < 6; k++) q[k] = FIX[k % 3].q;
    sf_sysone_answer a[6], b[6];
    int resets = 0, rc = 0;
    /* bitwise: timing on and off */
    if (reset_session(resets++, err, sizeof(err)) ||
        sf_sysone_decide(so, session, S1, q, 3, NULL, a, NULL, err, sizeof(err), NULL) ||
        reset_session(resets++, err, sizeof(err))) { fprintf(stderr, "timing: %s\n", err); return 1; }
    sf_sysone_timing tm;
    if (sf_sysone_decide(so, session, S1, q, 3, NULL, b, NULL, err, sizeof(err), &tm)) { fprintf(stderr, "timing: %s\n", err); return 1; }
    int same = 1;
    for (int k = 0; k < 3; k++) same &= logits_equal(&a[k], &b[k]);
    check(same, "timing on and off give bitwise equal logits");

    for (int st = 0; st < 2; st++) {
        for (int c = 0; c < 3; c++) {
            const int n = counts[c];
            double pre[3], sav[3], res[3], ev[3], phase[3], per_tok[3];
            int prefix_len = 0;
            for (int rep = 0; rep < 3; rep++) {
                if (reset_session(resets++, err, sizeof(err)) ||
                    sf_sysone_decide(so, session, states[st], q, n, NULL, a, &prefix_len, err, sizeof(err), &tm)) {
                    fprintf(stderr, "timing: %s\n", err);
                    rc = 1;
                    goto out;
                }
                char rbuf[256] = "", ebuf[256] = "";
                size_t ru = 0, eu = 0;
                double rsum = 0, esum = 0, msum = 0;
                int toks = 0;
                for (int k = 0; k < n; k++) {
                    ru += (size_t)snprintf(rbuf + ru, sizeof(rbuf) - ru, "%s%.0f", k ? "," : "", a[k].restore_ms);
                    eu += (size_t)snprintf(ebuf + eu, sizeof(ebuf) - eu, "%s%.0f", k ? "," : "", a[k].eval_ms);
                    rsum += a[k].restore_ms;
                    esum += a[k].eval_ms;
                    msum += a[k].ms;
                    toks += a[k].suffix_tokens;
                }
                pre[rep] = tm.prefill_ms;
                sav[rep] = tm.save_ms;
                res[rep] = rsum;
                ev[rep] = esum;
                phase[rep] = tm.save_ms + msum;
                per_tok[rep] = esum / toks;
                printf("timing state=%d q=%d rep=%d prefill=%.0f save=%.0f restore=[%s] eval=[%s] readout_total=%.0f eval_per_token=%.1f\n",
                       prefix_len, n, rep + 1, tm.prefill_ms, tm.save_ms, rbuf, ebuf, phase[rep], per_tok[rep]);
            }
            double mp = median(pre, 3), ms = median(sav, 3), mr = median(res, 3), me = median(ev, 3),
                   mq = median(phase, 3), mt = median(per_tok, 3);
            printf("timing median state=%d q=%d prefill=%.0f save=%.0f restore_sum=%.0f eval_sum=%.0f question_phase=%.0f "
                   "overhead_share=%.3f eval_per_token=%.1f\n",
                   prefix_len, n, mp, ms, mr, me, mq, mq > 0 ? (ms + mr) / mq : 0, mt);
            if (st == 0 && c == 0) printf("timing state=%d prefill per prefix token %.1f ms\n", prefix_len, mp / prefix_len);
        }
    }
    /* the short state again, without a reset in between: the session matches the prefix */
    for (int rep = 0; rep < 2; rep++) {
        if (sf_sysone_decide(so, session, S1, q, 3, NULL, a, NULL, err, sizeof(err), &tm)) { fprintf(stderr, "timing: %s\n", err); rc = 1; goto out; }
        printf("timing matched state=S1 q=3 run=%d prefill=%.0f save=%.0f eval=[%.0f,%.0f,%.0f]\n", rep + 1,
               tm.prefill_ms, tm.save_ms, a[0].eval_ms, a[1].eval_ms, a[2].eval_ms);
    }
out:
    free(big);
    check(rc == 0, "timing matrix");
    return rc || failures;
}

static int mode_checks(void) {
    char err[1024] = {0};
    sf_sysone_answer a[3], alone, again;

    /* fixtures: 1-3 share one state, asked together (exercises restore) */
    int all_ok = 1;
    for (int f = 0; f < 12;) {
        int n = (f == 0 || f == 6) ? (f == 0 ? 3 : 2) : 1;
        sf_sysone_question q[3];
        for (int k = 0; k < n; k++) q[k] = FIX[f + k].q;
        if (sf_sysone_decide(so, session, FIX[f].state, q, n, NULL, a, NULL, err, sizeof(err), NULL) != 0) {
            fprintf(stderr, "fixture %d: %s\n", f + 1, err);
            check(0, "decide fixtures");
            return 1;
        }
        for (int k = 0; k < n; k++) {
            int ok = fixture_ok(&FIX[f + k], &a[k]);
            all_ok &= ok;
            printf("sysone: fixture %2d top %d value %.3f confidence %.3f mass %.4f suffix %d %s\n",
                   f + k + 1, a[k].top, a[k].value, a[k].confidence, a[k].legal_mass,
                   a[k].suffix_tokens, ok ? "ok" : "WRONG");
        }
        f += n;
    }
    check(all_ok, "fixtures all 12 expected tops");
    check(1, "restore position and checkpoint after every snapshot load");

    /* isolation: fixture 1 alone vs third of three */
    sf_sysone_question q3[3] = {FIX[1].q, FIX[2].q, FIX[0].q};
    int rc = sf_sysone_decide(so, session, S1, &FIX[0].q, 1, NULL, &alone, NULL, err, sizeof(err), NULL);
    if (!rc) rc = sf_sysone_decide(so, session, S1, q3, 3, NULL, a, NULL, err, sizeof(err), NULL);
    if (rc) fprintf(stderr, "isolation: %s\n", err);
    check(!rc && logits_equal(&alone, &a[2]), "isolation fixture 1 alone == third of three, bitwise");

    /* determinism: the same request twice */
    rc = sf_sysone_decide(so, session, S1, &FIX[0].q, 1, NULL, &again, NULL, err, sizeof(err), NULL);
    check(!rc && logits_equal(&alone, &again), "determinism same request twice, bitwise");

    /* one option: answered without touching the session */
    static const char *const ONE[] = {"only"};
    sf_sysone_question one = {SF_SYSONE_CHOICE, "Pick.", 1, ONE, NULL};
    rc = sf_sysone_decide(so, session, S1, &one, 1, NULL, &again, NULL, err, sizeof(err), NULL);
    check(!rc && again.p[0] == 1.0 && again.legal_mass == 1.0 && again.suffix_tokens == 0, "one option p=1 without eval");

    /* timing: 60-token and 600-token states, three questions */
    sf_sysone_question t3[3] = {FIX[0].q, FIX[1].q, FIX[2].q};
    /* long first: the short state must start from an empty session, not a cached prefix */
    char *big = long_state(2000);
    if (big) { timed("long state", big, t3, 3); free(big); }
    timed("short state", S1, t3, 3);
    return failures ? 1 : 0;
}

/* a000: every frozen template version, on one engine (a process holds one). */
static int mode_checks_all(void) {
    char err[1024] = {0};
    printf("sysone: template %d\n", SF_SYSONE_TEMPLATE_VERSION);
    int rc = mode_checks();
    sf_sysone_close(so);
    so = NULL;
    if (sf_sysone_open(&so, engine, 1, err, sizeof(err)) != 0) {
        fprintf(stderr, "sysone: %s\n", err);
        check(0, "open template 1");
        return 1;
    }
    printf("sysone: template 1\n");
    return mode_checks() || rc;
}

int main(int argc, char **argv) {
    if (argc == 1) return math_checks();
    int rc = 1;
    if (open_all(argv[1])) {
        if (argc == 3 && !strcmp(argv[2], "--tokens")) rc = mode_tokens();
        else if (argc == 3 && !strcmp(argv[2], "--probe")) rc = mode_probe();
        else if (argc == 3 && !strcmp(argv[2], "--special-text")) rc = mode_special_text();
        else if (argc == 3 && !strcmp(argv[2], "--timing")) rc = mode_timing();
        else if (argc == 2) rc = mode_checks_all();
        else fprintf(stderr, "usage: %s [MODEL [--tokens|--probe|--special-text|--timing]]\n", argv[0]);
    }
    close_all();
    printf("sysone: %s\n", rc || failures ? "FAILED" : "all checks passed");
    return rc || failures;
}
