// iobench: pread-based disk benchmark with F_NOCACHE, mirroring ds4's read paths.
//   iobench write <file> <GiB>                         sequential write 8 MiB, per-GiB rate
//   iobench seq   <file> <bs> <threads> <GiB>          sequential read, each thread its own region
//   iobench rand  <file> <bs> <threads> <sec> [align]  random read over the whole file
//   iobench batch <file> <bs> <n> <threads> <reps>     n random reads issued together, wait for all
#include <fcntl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static uint64_t rng(uint64_t *s) { *s ^= *s << 13; *s ^= *s >> 7; *s ^= *s << 17; return *s; }
static int cmpd(const void *a, const void *b) { double x = *(double *)a, y = *(double *)b; return (x > y) - (x < y); }
static void full_pread(int fd, char *b, size_t n, off_t o) {
    while (n) { ssize_t r = pread(fd, b, n, o); if (r <= 0) { perror("pread"); exit(1); } b += r; n -= r; o += r; }
}

typedef struct { int fd; size_t bs; uint64_t size, align, n; off_t start; double stop, *lat; size_t nlat, cap; uint64_t seed; } job;

static void *seq_worker(void *a) {
    job *j = a; char *b; posix_memalign((void **)&b, 16384, j->bs);
    for (uint64_t i = 0; i < j->n; i++) full_pread(j->fd, b, j->bs, j->start + (off_t)(i * j->bs));
    free(b); return NULL;
}
static void *rand_worker(void *a) {
    job *j = a; char *b; posix_memalign((void **)&b, 16384, j->bs);
    uint64_t slots = (j->size - j->bs) / j->align;
    while (now() < j->stop) {
        off_t o = (off_t)(rng(&j->seed) % slots * j->align);
        double t = now(); full_pread(j->fd, b, j->bs, o); t = now() - t;
        if (j->nlat == j->cap) j->lat = realloc(j->lat, (j->cap = j->cap * 2 + 1024) * sizeof(double));
        j->lat[j->nlat++] = t;
    }
    free(b); return NULL;
}
static void *batch_worker(void *a) {  // j->n random 16K-aligned reads
    job *j = a; char *b; posix_memalign((void **)&b, 16384, j->bs);
    for (uint64_t i = 0; i < j->n; i++) full_pread(j->fd, b, j->bs, (off_t)(rng(&j->seed) % ((j->size - j->bs) / 16384) * 16384));
    free(b); return NULL;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: see source\n"); return 2; }
    const char *mode = argv[1], *path = argv[2];
    if (!strcmp(mode, "write")) {
        uint64_t gib = strtoull(argv[3], 0, 10), bs = 8 << 20;
        int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644); if (fd < 0) { perror(path); return 1; }
        fcntl(fd, F_NOCACHE, 1);
        char *b; posix_memalign((void **)&b, 16384, bs);
        uint64_t s = 88172645463325252ull; for (size_t i = 0; i < bs / 8; i++) ((uint64_t *)b)[i] = rng(&s);
        double t0 = now(), tg = t0;
        for (uint64_t i = 0; i < gib * 128; i++) {
            ((uint64_t *)b)[0] = i;  // every block distinct
            if (write(fd, b, bs) != (ssize_t)bs) { perror("write"); return 1; }
            if ((i + 1) % 128 == 0) { double t = now(); printf("GiB %3llu: %.2f GB/s\n", (i + 1) / 128, 1.073741824 / (t - tg)); fflush(stdout); tg = t; }
        }
        double tw = now(); fcntl(fd, F_FULLFSYNC); double tf = now();
        printf("WRITE total %.2f GB/s (incl. F_FULLFSYNC %.2fs)\n", gib * 1.073741824 / (tf - t0), tf - tw);
        close(fd); return 0;
    }
    int fd = open(path, O_RDONLY); if (fd < 0) { perror(path); return 1; }
    fcntl(fd, F_NOCACHE, 1); fcntl(fd, F_RDAHEAD, 0);
    struct stat st; fstat(fd, &st); uint64_t size = st.st_size;
    size_t bs = strtoull(argv[3], 0, 10); int th = atoi(argv[4]);
    pthread_t t[256]; job j[256];
    if (!strcmp(mode, "seq")) {
        uint64_t per = (uint64_t)(atof(argv[5]) * 1073741824.0) / th / bs, region = size / th / bs * bs;
        double t0 = now();
        for (int i = 0; i < th; i++) { j[i] = (job){.fd = fd, .bs = bs, .n = per, .start = (off_t)(i * region)}; pthread_create(&t[i], 0, seq_worker, &j[i]); }
        for (int i = 0; i < th; i++) pthread_join(t[i], 0);
        printf("SEQ bs=%zu th=%d: %.2f GB/s\n", bs, th, per * bs * th / (now() - t0) / 1e9);
    } else if (!strcmp(mode, "rand")) {
        double sec = atof(argv[5]); uint64_t align = argc > 6 ? strtoull(argv[6], 0, 10) : 4096;
        double t0 = now();
        for (int i = 0; i < th; i++) { j[i] = (job){.fd = fd, .bs = bs, .size = size, .align = align, .stop = t0 + sec, .seed = 0x9E3779B97F4A7C15ull * (i + 1) + (uint64_t)(t0 * 1e6)}; pthread_create(&t[i], 0, rand_worker, &j[i]); }
        size_t n = 0;
        for (int i = 0; i < th; i++) { pthread_join(t[i], 0); n += j[i].nlat; }
        double dt = now() - t0, *all = malloc(n * sizeof(double)), sum = 0; size_t k = 0;
        for (int i = 0; i < th; i++) { memcpy(all + k, j[i].lat, j[i].nlat * sizeof(double)); k += j[i].nlat; }
        qsort(all, n, sizeof(double), cmpd);
        for (size_t i = 0; i < n; i++) sum += all[i];
        printf("RAND bs=%zu th=%d: %.0f IOPS %.2f GB/s lat avg %.0f p50 %.0f p99 %.0f us\n", bs, th, n / dt, n * bs / dt / 1e9,
               sum / n * 1e6, all[n / 2] * 1e6, all[(size_t)(n * 0.99)] * 1e6);
    } else if (!strcmp(mode, "batch")) {
        int n = th; th = atoi(argv[5]); int reps = atoi(argv[6]), nt = th < n ? th : n;
        double *w = malloc(reps * sizeof(double)); uint64_t seed = (uint64_t)(now() * 1e6) | 1;
        for (int r = 0; r < reps; r++) {
            double t0 = now();
            for (int i = 0; i < nt; i++) { j[i] = (job){.fd = fd, .bs = bs, .size = size, .n = n / nt + (i < n % nt), .seed = rng(&seed)}; pthread_create(&t[i], 0, batch_worker, &j[i]); }
            for (int i = 0; i < nt; i++) pthread_join(t[i], 0);
            w[r] = now() - t0;
        }
        qsort(w, reps, sizeof(double), cmpd);
        printf("BATCH %d x %zu B th=%d: median %.2f ms p90 %.2f ms -> %.2f GB/s\n", n, bs, th, w[reps / 2] * 1e3, w[reps * 9 / 10] * 1e3,
               (double)n * bs / w[reps / 2] / 1e9);
    }
    return 0;
}
