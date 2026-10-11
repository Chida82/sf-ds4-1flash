// fanboost: protezione termica aggiuntiva per Mac Apple Silicon (provato su M5 Max).
// Il controllo resta ad Apple. Se chip, SSD o batteria superano la soglia ON, le ventole
// vanno al 100% finché tutto torna sotto la soglia OFF: mai sotto la curva Apple.
// Un processo qualsiasi, senza root, può chiedere il 100% subito con `fanboost max`:
// la richiesta vale TTL secondi e si rinnova ripetendo max.
//
//   fanboost               monitor: stampa letture e decisioni, non scrive mai
//   fanboost status        stato attuale: demone, termica, richiesta, ventole, temperature
//   fanboost check         esce 0 se il demone è attivo, 1 (con una riga su stderr) se no
//   fanboost help          elenco dei comandi (anche per un comando sbagliato)
//   fanboost max           ventole al 100% subito, per TTL secondi (rinnovabile)
//   fanboost release       ritira la richiesta: ventole al 100% per almeno TAIL s, poi termica o curva Apple
//   fanboost resume        accende la protezione termica (all'avvio del demone è in pausa)
//   fanboost pause         la rispegne; max/release funzionano sempre
//   fanboost run           il demone (lo lancia launchd)
//   make test              self-test della logica
//   sudo make install      installa e avvia il demone
//   /usr/bin/log show --last 1d --predicate 'subsystem == "com.chida82.fanboost"'
#include <IOKit/IOKitLib.h>
#include <os/log.h>
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <notify.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

// Soglie in °C: manopole di calibrazione.
enum { CHIP, SSD, BATT, NS };
static const char *NAME[NS] = {"chip", "ssd", "batteria"};
static const float ON[NS]  = {85, 68, 38};
static const float OFF[NS] = {75, 64, 35};
#define PERIOD 2  // secondi tra le letture
#define ENTER 15  // secondi consecutivi sopra soglia ON prima di ogni BOOST
#define HOLD 10   // secondi minimi in BOOST
#define TTL 10    // secondi di validità di un max
#define TAIL 3    // secondi minimi al 100% dopo un release (inerzia termica, niente impulsi); con le letture ~4 s
#define MAXFANS 8
// Richiesta diretta: il file porta l'ora dell'ultimo max (mtime), la notifica sveglia il demone.
// Termica: lo stato della notifica, 1 = attiva (resume), 0 = pausa. Lo tiene notifyd finché qualcuno
// è registrato; all'avvio il demone lo azzera: dopo riavvio, installazione o crash si parte in pausa.
#define LEASE "/tmp/fanboost.lease"
#define NOTE "com.chida82.fanboost"
// Il demone pubblica qui a ogni giro cosa sta facendo, per `fanboost status`. Lo stato sparisce
// quando il demone muore: senza ST_UP il demone non è attivo.
#define NOTE_STATE "com.chida82.fanboost.state"
enum { ST_UP = 1, ST_PAUSE = 2, ST_HOT = 4, ST_WAIT = 8, ST_TAIL = 16, ST_BOOST = 32 };

typedef struct { char major, minor, build, reserved; uint16_t release; } SMCVers;
typedef struct { uint16_t version, length; uint32_t cpu, gpu, mem; } SMCPLimit;
typedef struct { uint32_t size, type; char attr; } SMCKeyInfo;
typedef struct { uint32_t key; SMCVers vers; SMCPLimit plimit; SMCKeyInfo info; char result, status, cmd; uint32_t data32; unsigned char bytes[32]; } SMCParam;
typedef struct { uint32_t key; SMCKeyInfo info; } Key;

static io_connect_t con;
static os_log_t lg;
static volatile sig_atomic_t quit;
static int dry, nfans, ns[NS];
static Key sens[NS][256], fmd[MAXFANS], ftg[MAXFANS], fac[MAXFANS], fmx[MAXFANS];

static uint32_t fourcc(const char *s) { return s[0] << 24 | s[1] << 16 | s[2] << 8 | s[3]; }
static int smc(SMCParam *in, SMCParam *out) { size_t n = sizeof *out; return IOConnectCallStructMethod(con, 2, in, sizeof *in, out, &n) != kIOReturnSuccess || out->result; }
static int lookup(uint32_t k, Key *key) { SMCParam in = {.key = k, .cmd = 9}, out = {0}; if (smc(&in, &out)) return -1; key->key = k; key->info = out.info; return 0; }
static int rd(const Key *k, void *v) { SMCParam in = {.key = k->key, .cmd = 5, .info = k->info}, out = {0}; if (smc(&in, &out)) return -1; memcpy(v, out.bytes, k->info.size); return 0; }
static float rdf(const Key *k) { float v = 0; rd(k, &v); return v; }

static int wr(const Key *k, const void *v) {
  for (int i = 0; i < 10; i++) {  // l'SMC a volte rifiuta la prima scrittura
    SMCParam in = {.key = k->key, .cmd = 6, .info = k->info}, out = {0};
    memcpy(in.bytes, v, k->info.size);
    if (!smc(&in, &out)) return 0;
    usleep(100000);
  }
  char n[5] = {k->key >> 24, k->key >> 16, k->key >> 8, k->key, 0};
  os_log_error(lg, "scrittura SMC fallita: %{public}s", n);
  return -1;
}

static int fankey(int i, const char *suffix, Key *k) { char n[5]; snprintf(n, sizeof n, "F%d%s", i, suffix); return lookup(fourcc(n), k); }

// AUTO = curva Apple: modalità 0 e target 0 (come Stats su M5).
static void set_auto(void) {
  unsigned char zero = 0; float fz = 0;
  for (int i = 0; i < nfans; i++) { wr(&fmd[i], &zero); wr(&ftg[i], &fz); }
}

// BOOST: target al massimo, poi modalità manuale. In quest'ordine non c'è mai un istante in manuale
// con target 0, cioè sotto la curva Apple. Riscritto a ogni lettura: se l'SMC torna in auto lo riprendiamo.
static void set_max(int i) { unsigned char one = 1; float mx = rdf(&fmx[i]); wr(&ftg[i], &mx); wr(&fmd[i], &one); }

static float maxof(int g) {
  float m = 0, v;
  for (int i = 0; i < ns[g]; i++) if (!rd(&sens[g][i], &v) && v > m && v < 150) m = v;
  return m;
}

// Protezione termica, indipendente dalle richieste.
typedef struct { int boost; long since, above; } State;
#define STATE_INIT {.above = -1}

// Ritorna il sensore che ha attivato il BOOST, -2 al ritorno in AUTO, -1 se nulla cambia.
static int update(State *s, const float t[NS], long now) {
  if (!s->boost) {
    int hot = -1;
    for (int i = 0; i < NS && hot < 0; i++) if (t[i] >= ON[i]) hot = i;
    if (hot < 0) { s->above = -1; return -1; }  // un calo azzera l'attesa
    if (s->above < 0) s->above = now;
    if (now - s->above < ENTER) return -1;
    s->boost = 1; s->since = now; s->above = -1;
    return hot;
  }
  if (now - s->since < HOLD) return -1;
  for (int i = 0; i < NS; i++) if (t[i] > OFF[i]) return -1;
  s->boost = 0;
  return -2;
}

// Richiesta attiva se l'ultimo max (mtime, ora di sistema) ha meno di TTL secondi.
// Un mtime nel futuro oltre una lettura (orologio spostato, touch -t) non vale.
static int lease_active(long mtime, long now) { return mtime > 0 && now - mtime < TTL && mtime - now <= PERIOD; }

// Richiesta vista dal demone. release (file sparito mentre era attiva) tiene il 100% per almeno TAIL s;
// una scadenza no, i TTL s del max sono già la coda. Ritorna 1 se la richiesta vuole il 100%.
typedef struct { int on; long tail; } Req;
static int req_step(Req *r, long mtime, long wall, long mono) {
  int on = lease_active(mtime, wall);
  if (r->on && !on && !mtime) r->tail = mono + TAIL;
  r->on = on;
  return on || mono < r->tail;
}

// Il demone non apre mai il file: lstat e basta, solo file regolari.
static long lease_mtime(void) { struct stat st; return !lstat(LEASE, &st) && S_ISREG(st.st_mode) ? (long)st.st_mtime : 0; }

// Ventole: 100% se la termica o la richiesta lo chiedono (OR). 1 all'accensione, -1 allo spegnimento.
typedef struct { int on; } Fans;
static int fans_step(Fans *f, int want) {
  if (want == f->on) return 0;
  f->on = want;
  return want ? 1 : -1;
}

static void selftest(void) {
  State s = STATE_INIT;
  float cool[NS] = {60, 40, 30}, hot[NS] = {60, 40, 39}, mid[NS] = {80, 40, 30};
  assert(update(&s, cool, 0) == -1 && !s.boost);
  assert(update(&s, hot, 0) == -1 && !s.boost);                 // picco: serve ENTER
  assert(update(&s, cool, 2) == -1);                             // calo: attesa azzerata
  assert(update(&s, hot, 4) == -1 && update(&s, hot, 18) == -1); // 14 s sopra: non basta
  assert(update(&s, hot, 19) == BATT && s.boost);
  assert(update(&s, cool, 23) == -1 && s.boost);                 // HOLD non ancora passato
  assert(update(&s, mid, 29) == -1 && s.boost);                  // chip tra OFF e ON: resta BOOST
  assert(update(&s, cool, 31) == -2 && !s.boost);
  assert(update(&s, hot, 33) == -1 && update(&s, hot, 47) == -1); // riattivazione: di nuovo ENTER
  assert(update(&s, hot, 48) == BATT);

  assert(!lease_active(0, 100));                                 // nessun max
  assert(lease_active(100, 100) && lease_active(100, 109));      // max: vale subito, per TTL
  assert(!lease_active(100, 110));                               // scaduto: come release
  assert(lease_active(108, 110));                                // max rinnovato: riparte il conto
  assert(lease_active(102, 100) && !lease_active(200, 100));     // futuro: tollerato solo entro PERIOD

  Req r = {0};
  assert(!req_step(&r, 0, 100, 50));                             // nessun max
  assert(req_step(&r, 100, 100, 50) && r.on);                    // max
  assert(req_step(&r, 0, 102, 52) && !r.on);                     // release: ancora al 100%
  assert(req_step(&r, 0, 104, 54) && !req_step(&r, 0, 105, 55)); // per TAIL s, poi basta
  assert(req_step(&r, 106, 106, 56) && req_step(&r, 0, 107, 57)); // max nella coda, poi release: nuova coda
  r = (Req){0};
  assert(req_step(&r, 100, 100, 50) && !req_step(&r, 100, 110, 60)); // scaduto: nessuna coda
  assert(!req_step(&r, 0, 111, 61));                             // release dopo la scadenza: niente

  Fans f = {0};
  State th = STATE_INIT;
  assert(fans_step(&f, th.boost || 1) == 1 && f.on);             // max: subito, senza ENTER
  assert(fans_step(&f, th.boost || 1) == 0);                     // max rinnovato: nessun cambio
  th.boost = 1;
  assert(fans_step(&f, th.boost || 0) == 0 && f.on);         // release con termica attiva: resta 100%
  th.boost = 0;
  assert(fans_step(&f, th.boost || 0) == -1 && !f.on);       // né termica né richiesta: AUTO
  puts("ok");
}

static long now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec; }
static void onsig(int sig) { (void)sig; quit = 1; }
static void onwake(int sig) { (void)sig; }  // interrompe sleep(): max/release/pause/resume si applicano subito

// max/release: nessun privilegio. Il file porta l'ora, la notifica sveglia il demone.
// Un max su richiesta già attiva è un rinnovo: tocca solo il file, il demone lo vede alla lettura
// successiva. Così centinaia di max al secondo non lo svegliano centinaia di volte.
static int request(int on) {
  if (on) {
    int renew = lease_active(lease_mtime(), (long)time(NULL));
    int fd = open(LEASE, O_WRONLY | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0644);
    if (fd < 0 || futimes(fd, NULL)) { perror(LEASE); if (fd >= 0) close(fd); return 1; }
    close(fd);
    if (renew) return 0;
  } else if (unlink(LEASE) && errno != ENOENT) {
    perror(LEASE);
    return 1;
  }
  notify_post(NOTE);
  return 0;
}

// resume/pause: nessun privilegio, la protezione è in più (in pausa resta la curva Apple).
static int thermal_set(int on) {
  int t;
  if (notify_register_check(NOTE, &t) || notify_set_state(t, on) || notify_post(NOTE)) { fputs("notifica non riuscita\n", stderr); return 1; }
  return 0;
}

static int help(FILE *out) {
  fprintf(out,
    "fanboost: ventole al 100%% quando serve, poi di nuovo alla curva Apple (la sicurezza resta ad Apple)\n\n"
    "  fanboost            monitor: letture e decisioni ogni %d s, non scrive mai\n"
    "  fanboost status     stato attuale: demone, termica, richiesta, ventole, temperature\n"
    "  fanboost check      esce 0 se il demone è attivo, 1 se no (per gli script)\n"
    "  fanboost max        ventole al 100%% subito per %d s; ripetuto, rinnova\n"
    "  fanboost release    ritira la richiesta: ventole al 100%% ancora per almeno %d s\n"
    "  fanboost resume     accende la protezione termica (all'avvio del demone è in pausa)\n"
    "  fanboost pause      la rispegne; max e release funzionano sempre\n"
    "  fanboost help       questo elenco\n"
    "  fanboost run        il demone (lo lancia launchd)\n"
    "  fanboost -t         self-test\n\n"
    "log: /usr/bin/log show --last 1d --predicate 'subsystem == \"com.chida82.fanboost\"'\n",
    PERIOD, TTL, TAIL);
  return out == stdout ? 0 : 1;
}

// Legge senza root: stato pubblicato dal demone, lease, SMC. Non scrive mai, non logga.
// Stato pubblicato dal demone; 0 se il demone non c'è.
static uint64_t daemon_state(void) {
  int tk; uint64_t st = 0;
  if (notify_register_check(NOTE_STATE, &tk) == NOTIFY_STATUS_OK) notify_get_state(tk, &st);
  return st;
}

static int status(void) {
  uint64_t st = daemon_state();
  int up = st & ST_UP;
  printf("demone      %s\n", up ? "attivo" : "NON attivo: niente boost (sudo make install, oppure riavvio)");
  if (up) printf("termica     %s\n", st & ST_PAUSE ? "in pausa (fanboost resume per accenderla)"
                                     : st & ST_HOT ? "attiva, BOOST: un sensore ha superato la soglia ON"
                                     : st & ST_WAIT ? "attiva, un sensore è sopra la soglia ON: BOOST se ci resta 15 s"
                                     : "attiva, sotto soglia");
  long m = lease_mtime(), w = time(NULL);
  if (lease_active(m, w)) printf("richiesta   max attiva, scade tra %ld s se non rinnovata\n", TTL - (w - m));
  else if (up && st & ST_TAIL) printf("richiesta   release: ventole al 100%% ancora per qualche secondo\n");
  else printf("richiesta   nessuna\n");
  unsigned char md = 0;
  rd(&fmd[0], &md);
  printf("ventole     %s\n", !md ? "AUTO (curva Apple)" : !up ? "manuali, ma il demone non è attivo"
                           : st & ST_HOT ? "BOOST (termica)" : st & ST_TAIL ? "BOOST (coda dopo release)" : "BOOST (richiesta)");
  for (int i = 0; i < nfans; i++) {
    unsigned char mi = 0; rd(&fmd[i], &mi);
    printf("  F%d        %4.0f giri  (target %.0f, max %.0f, %s)\n", i, rdf(&fac[i]), rdf(&ftg[i]), rdf(&fmx[i]), mi ? "manuale" : "auto");
  }
  for (int g = 0; g < NS; g++)
    if (ns[g]) printf("%-11s %5.1f °C  (ON %.0f, OFF %.0f)\n", NAME[g], maxof(g), ON[g], OFF[g]);
  return 0;
}

int main(int argc, char **argv) {
  const char *cmd = argc > 1 ? argv[1] : "";
  if (!strcmp(cmd, "help") || !strcmp(cmd, "-h") || !strcmp(cmd, "--help")) return help(stdout);
  if (*cmd && strcmp(cmd, "run") && strcmp(cmd, "status") && strcmp(cmd, "check") && strcmp(cmd, "-t") && strcmp(cmd, "max") &&
      strcmp(cmd, "release") && strcmp(cmd, "pause") && strcmp(cmd, "resume")) {
    fprintf(stderr, "comando sconosciuto: %s\n\n", cmd);
    return help(stderr);
  }
  if (!strcmp(cmd, "-t")) { selftest(); return 0; }
  if (!strcmp(cmd, "max") || !strcmp(cmd, "release")) return request(!strcmp(cmd, "max"));
  // pause: il demone resta vivo (solo lui può scrivere le ventole) ma smette di valutare la termica.
  if (!strcmp(cmd, "pause") || !strcmp(cmd, "resume")) return thermal_set(!strcmp(cmd, "resume"));
  // check: solo l'esito, per chi chiede max e deve sapere se qualcuno lo ascolta.
  if (!strcmp(cmd, "check")) {
    if (daemon_state() & ST_UP) return 0;
    fputs("demone fanboost NON attivo (sudo make install, oppure riavvio)\n", stderr);
    return 1;
  }
  lg = os_log_create("com.chida82.fanboost", "daemon");
  dry = geteuid() != 0 || strcmp(cmd, "run");

  io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSMC"));
  if (!svc || IOServiceOpen(svc, mach_task_self(), 0, &con)) { fputs("AppleSMC non disponibile\n", stderr); return 1; }

  Key k;
  unsigned char b[4] = {0}, nf = 0;
  if (!lookup(fourcc("#KEY"), &k)) rd(&k, b);
  uint32_t nkeys = b[0] << 24 | b[1] << 16 | b[2] << 8 | b[3];
  for (uint32_t i = 0; i < nkeys; i++) {
    SMCParam in = {.cmd = 8, .data32 = i}, out = {0};
    if (smc(&in, &out) || lookup(out.key, &k) || k.info.type != fourcc("flt ")) continue;
    uint32_t p = out.key >> 16;
    int g = p == ('T' << 8 | 'p') || p == ('T' << 8 | 'g') ? CHIP
          : out.key == fourcc("TH0x") ? SSD
          : out.key == fourcc("TB0T") || out.key == fourcc("TB1T") || out.key == fourcc("TB2T") ? BATT : -1;
    if (g >= 0 && ns[g] < 256) sens[g][ns[g]++] = k;
  }

  if (!lookup(fourcc("FNum"), &k)) rd(&k, &nf);
  nfans = nf > MAXFANS ? MAXFANS : nf;
  for (int i = 0; i < nfans; i++)
    if ((fankey(i, "md", &fmd[i]) && fankey(i, "Md", &fmd[i])) || fankey(i, "Tg", &ftg[i]) || fankey(i, "Ac", &fac[i]) || fankey(i, "Mx", &fmx[i])) {
      fprintf(stderr, "chiavi ventola %d non trovate\n", i); return 1;
    }
  if (!ns[CHIP] || !nfans) { fputs("sensori chip o ventole non trovati\n", stderr); return 1; }
  if (!strcmp(cmd, "status")) return status();

  os_log(lg, "avvio: %d sensori chip, %d ssd, %d batteria, %d ventole%{public}s", ns[CHIP], ns[SSD], ns[BATT], nfans, dry ? " (dry-run)" : "");
  struct sigaction sa = {.sa_handler = onsig};
  sigaction(SIGTERM, &sa, NULL); sigaction(SIGINT, &sa, NULL); sigaction(SIGHUP, &sa, NULL);
  // max/release/pause/resume mandano NOTE: SIGUSR1 interrompe sleep() e il ciclo riparte subito.
  struct sigaction wk = {.sa_handler = onwake};
  sigaction(SIGUSR1, &wk, NULL);
  int note = -1;
  if (notify_register_signal(NOTE, SIGUSR1, &note) != NOTIFY_STATUS_OK)
    os_log_error(lg, "notifica %{public}s non registrata: max/release entro %d s, termica in pausa", NOTE, PERIOD);
  if (!dry) set_auto();  // parti sempre pulito, anche dopo un crash
  if (!dry) notify_set_state(note, 0);  // si parte in pausa; la termica la accende resume
  int stk = -1;
  if (!dry) notify_register_check(NOTE_STATE, &stk);

  State s = STATE_INIT;
  Fans f = {0};
  Req rq = {0};
  int paused = -1;  // il primo giro registra lo stato di partenza
  while (!quit) {
    float t[NS];
    for (int g = 0; g < NS; g++) t[g] = maxof(g);
    long mono = now();
    uint64_t ps = 0;
    notify_get_state(note, &ps);  // registrazione fallita: resta 0, pausa
    int pz = !ps;
    if (pz != paused) os_log(lg, "%{public}s", pz ? "pause: termica spenta, richieste attive" : "resume: termica attiva");
    paused = pz;
    int ev = -1;
    if (paused) s = (State)STATE_INIT;  // niente termica; a resume si riparte da ENTER
    else ev = update(&s, t, mono);
    if (ev >= 0) os_log(lg, "termica: %{public}s %.1f°C (soglia %.0f)", NAME[ev], t[ev], ON[ev]);
    else if (ev == -2) os_log(lg, "termica rientrata: chip %.1f ssd %.1f batteria %.1f °C", t[CHIP], t[SSD], t[BATT]);
    long m = lease_mtime();
    int was = rq.on, req = req_step(&rq, m, (long)time(NULL), mono);
    if (rq.on && !was) os_log(lg, "richiesta: max");
    else if (!rq.on && was && m) os_log(lg, "richiesta: scaduta");
    else if (!rq.on && was) os_log(lg, "richiesta: release, ventole al 100%% per almeno %d s", TAIL);
    int ch = fans_step(&f, s.boost || req);
    if (ch > 0) {
      os_log(lg, "BOOST (%{public}s)", s.boost ? "termica" : "richiesta");
    } else if (ch < 0) {
      if (!dry) set_auto();
      os_log(lg, "AUTO: chip %.1f ssd %.1f batteria %.1f °C", t[CHIP], t[SSD], t[BATT]);
    }
    if (f.on && !dry)
      for (int i = 0; i < nfans; i++) set_max(i);
    if (!dry) notify_set_state(stk, ST_UP | (paused ? ST_PAUSE : 0) | (s.boost ? ST_HOT : 0) | (s.above >= 0 ? ST_WAIT : 0) |
                                    (!rq.on && req ? ST_TAIL : 0) | (f.on ? ST_BOOST : 0));
    if (dry) {
      printf("chip %.1f  ssd %.1f  batteria %.1f  termica %s  richiesta %s  -> %s", t[CHIP], t[SSD], t[BATT],
             paused ? "pausa" : s.boost ? "si" : "no", rq.on ? "si" : req ? "coda" : "no", f.on ? "BOOST" : "AUTO");
      for (int i = 0; i < nfans; i++) printf("  F%d %.0f rpm", i, rdf(&fac[i]));
      puts("");
    }
    sleep(PERIOD);
  }
  if (!dry) { set_auto(); notify_set_state(stk, 0); }
  os_log(lg, "uscita");
  return 0;
}
