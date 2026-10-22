/* nandfs: a FUSE filesystem whose only built-in physics are the NAND gate and
 * the D flip-flop. Everything else -- adders, counters, whole computers -- is
 * folders and symlinks in the backing directory.
 *
 * The mount is a passthrough view of a backing directory, plus:
 *   X.nand/out    NAND of the signals the symlinks X.nand/a and X.nand/b point at
 *   X.dff/q       flip-flop state; takes the value of X.dff/d on every clock tick
 *   X.pin/out     the bit stored in the regular file X.pin/value
 *   X.bus/value   the symlinks X.bus/0, X.bus/1, ... read (or written) as one number
 *   X.mem/rN      bit N (0-31) of the 32-bit word at the address given by the
 *                 symlinks X.mem/a0, a1, ...: an array of words kept in the
 *                 host file X.mem/data, which is mapped into the daemon. On a
 *                 clock tick, each byte k whose enable X.mem/we<k> is 1 takes
 *                 bits 8k..8k+7 of X.mem/w0..w31. (The one exception to "NAND
 *                 and flip-flops only": a large array of bits kept in a file.)
 *   /vcc/out, /gnd/out   constants 1 and 0
 *   /clk/out      the clock, for flip-flops built out of gates
 *   /.ctl/        clock, run, reset, reload, stats, profile
 *
 * One clock tick: every flip-flop samples d at once and updates q; the gates
 * settle; clk goes high and the gates settle; clk goes low and the gates settle.
 *
 * The tree is loaded into arrays (re-read after any edit) and only gates
 * whose inputs changed are re-evaluated. A wire that leads nowhere reads as 0.
 * Nothing here knows what circuit it runs.
 */
#define FUSE_USE_VERSION 31
#define _GNU_SOURCE
#include <fuse.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

enum { T_VCC, T_GND, T_CLK, T_NAND, T_DFF, T_PIN, T_BUS, T_MEM, T_MEMR };

#define WORD_BITS 32
#define MAX_ADDR_BITS 40

typedef struct { int *v; int n, cap; } ivec;

static void ipush(ivec *a, int x) {
    if (a->n == a->cap) {
        a->cap = a->cap ? a->cap * 2 : 16;
        a->v = realloc(a->v, a->cap * sizeof(int));
    }
    a->v[a->n++] = x;
}

/* A .mem folder: its word array (data, mapped from the file) and the nodes
 * wired to its address, write data and byte enables. Its read bits are nodes
 * of type T_MEMR, r0 .. r0+31, named X.mem/r0 .. X.mem/r31. */
typedef struct {
    int fd, na, r0;
    uint8_t *data;
    size_t size;
    int a[MAX_ADDR_BITS], w[WORD_BITS], we[WORD_BITS / 8];
} Mem;

/* The loaded circuit. Node i is the primitive folder path[i] (or, for a read
 * bit of a .mem, the file X.mem/rN); 0-2 are vcc, gnd, clk. */
typedef struct {
    int n;
    char **path;
    uint8_t *type, *val, *init;
    int *ia, *ib;              /* input nodes (a/b for a gate, d for a flip-flop);
                                  for a read bit, its .mem and bit number */
    int *fo_off, *fo;          /* fanout lists */
    int *lvl;                  /* gate depth, ignoring feedback wires */
    uint8_t *queued, *cand;
    uint32_t *busy;            /* evaluations per node while profiling */
    int hcap, *htab;           /* path -> node */
    ivec gates, dffs, reads, *bucket, candlist;
    int npins, nbroken, maxlvl, cyclic, lo, hi, nmems;
    Mem *mems;
} Net;

static int bfd;                                 /* backing directory */
static pthread_mutex_t M = PTHREAD_MUTEX_INITIALIZER;
static Net *net;
static volatile int dirty = 1;
static volatile double last_edit;               /* time of the last structural edit */
static volatile double run_hz;
static uint64_t ticks, evals, reloads, oscillations;
static int profiling;
static double load_ms, rate_ticks, rate_evals;

/* Filesystem requests take the lock through lock(), which lets the clock
 * thread see that someone is waiting and step aside between ticks. */
static volatile int waiting;

static void lock(void) {
    __sync_fetch_and_add(&waiting, 1);
    pthread_mutex_lock(&M);
    __sync_fetch_and_sub(&waiting, 1);
}

static void unlock(void) { pthread_mutex_unlock(&M); }

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

/* ---------- paths ---------- */

static int prim_type(const char *name) {
    static const struct { const char *s; int t; } sfx[] = {
        { ".nand", T_NAND }, { ".dff", T_DFF }, { ".pin", T_PIN }, { ".bus", T_BUS },
        { ".mem", T_MEM } };
    size_t n = strlen(name);
    for (size_t i = 0; i < sizeof sfx / sizeof *sfx; i++) {
        size_t k = strlen(sfx[i].s);
        if (n > k && !strcmp(name + n - k, sfx[i].s)) return sfx[i].t;
    }
    return -1;
}

static const char *rel(const char *p) { return p[1] ? p + 1 : "."; }

/* Lexically clean an absolute path. Fails if it climbs above the root. */
static int norm(const char *in, char *out) {
    size_t o = 0;
    out[0] = 0;
    for (const char *s = in; *s;) {
        while (*s == '/') s++;
        if (!*s) break;
        const char *e = strchr(s, '/');
        size_t L = e ? (size_t)(e - s) : strlen(s);
        if (L == 1 && s[0] == '.') {
        } else if (L == 2 && s[0] == '.' && s[1] == '.') {
            if (!o) return -1;
            while (out[o - 1] != '/') o--;
            out[--o] = 0;
        } else {
            if (o + L + 2 >= PATH_MAX) return -1;
            out[o++] = '/';
            memcpy(out + o, s, L);
            o += L;
            out[o] = 0;
        }
        s += L;
    }
    if (!o) strcpy(out, "/");
    return 0;
}

static uint32_t hash(const char *s) {
    uint32_t h = 2166136261u;
    while (*s) h = (h ^ (uint8_t)*s++) * 16777619u;
    return h;
}

static int lookup(Net *n, const char *p) {
    for (uint32_t h = hash(p) & (n->hcap - 1);; h = (h + 1) & (n->hcap - 1)) {
        int i = n->htab[h];
        if (i < 0 || !strcmp(n->path[i], p)) return i;
    }
}

/* Follow a wire: the symlink text `target`, found in folder `dir`, to the
 * primitive whose out (or q) it names. Symlinks along the way, such as a
 * module's output port, are followed. Returns -1 for a broken wire. */
static int resolve(Net *n, const char *dir, const char *target) {
    char p[PATH_MAX], q[PATH_MAX], lk[PATH_MAX];
    if (target[0] == '/') snprintf(p, sizeof p, "%s", target);
    else snprintf(p, sizeof p, "%s/%s", dir, target);
    for (int hop = 0; hop < 40; hop++) {
        if (norm(p, q) < 0) return -1;
        char *slash = strrchr(q, '/');
        if (slash != q && (!strcmp(slash, "/out") || !strcmp(slash, "/q"))) {
            *slash = 0;
            int i = lookup(n, q);
            if (i >= 0 && (n->type[i] == T_DFF) == (slash[1] == 'q')) return i;
            *slash = '/';
        }
        if (slash != q && slash[1] == 'r' && slash[2] >= '0' && slash[2] <= '9') {
            int i = lookup(n, q);
            if (i >= 0 && n->type[i] == T_MEMR) return i;
        }
        int found = 0;
        for (char *c = q + 1;; c++) {
            if (*c && *c != '/') continue;
            char save = *c;
            *c = 0;
            ssize_t L = readlinkat(bfd, q + 1, lk, sizeof lk - 1);
            if (L >= 0) {
                lk[L] = 0;
                *strrchr(q, '/') = 0;
                const char *rest = save ? c + 1 : "";
                if (lk[0] == '/') snprintf(p, sizeof p, "%s%s%s", lk, save ? "/" : "", rest);
                else snprintf(p, sizeof p, "%s/%s%s%s", q, lk, save ? "/" : "", rest);
                found = 1;
                break;
            }
            *c = save;
            if (!save) break;
        }
        if (!found) return -1;
    }
    return -1;
}

static int read_bit(int dfd, const char *name, int dflt) {
    char c;
    int fd = openat(dfd, name, O_RDONLY);
    if (fd < 0) return dflt;
    int r = read(fd, &c, 1) == 1 ? c == '1' : 0;
    close(fd);
    return r;
}

static char *read_link(int dfd, const char *name) {
    char buf[PATH_MAX];
    ssize_t L = readlinkat(dfd, name, buf, sizeof buf - 1);
    if (L < 0) return NULL;
    buf[L] = 0;
    return strdup(buf);
}

/* ---------- loading the tree ---------- */

typedef struct { char *path, *la, *lb; int type; uint8_t init; } Raw;
static Raw *raw;
static int nraw, capraw;

static void add_raw(Raw r) {
    if (nraw == capraw) raw = realloc(raw, (capraw = capraw ? capraw * 2 : 1024) * sizeof *raw);
    raw[nraw++] = r;
}

/* Wire names of a .mem folder: a0.., w0..w31, we0..we3. */
static void mem_link_name(char *buf, size_t sz, int k) {
    if (k < MAX_ADDR_BITS) snprintf(buf, sz, "a%d", k);
    else if (k < MAX_ADDR_BITS + WORD_BITS) snprintf(buf, sz, "w%d", k - MAX_ADDR_BITS);
    else snprintf(buf, sz, "we%d", k - MAX_ADDR_BITS - WORD_BITS);
}
#define MEM_LINKS (MAX_ADDR_BITS + WORD_BITS + WORD_BITS / 8)

static void walk(const char *abs) {
    int fd = openat(bfd, rel(abs[0] ? abs : "/"), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    if (fd < 0) return;
    DIR *d = fdopendir(fd);
    struct dirent *e;
    while ((e = readdir(d))) {
        const char *nm = e->d_name;
        if (nm[0] == '.' && (!nm[1] || (nm[1] == '.' && !nm[2]))) continue;
        int isdir = e->d_type == DT_DIR;
        if (e->d_type == DT_UNKNOWN) {
            struct stat st;
            isdir = !fstatat(fd, nm, &st, AT_SYMLINK_NOFOLLOW) && S_ISDIR(st.st_mode);
        }
        if (!isdir) continue;
        char p[PATH_MAX];
        snprintf(p, sizeof p, "%s/%s", abs, nm);
        int t = prim_type(nm);
        if (t < 0) { walk(p); continue; }
        if (t == T_BUS) continue;
        if (t == T_MEM) {
            for (int k = 0; k < WORD_BITS; k++) {
                char rp[PATH_MAX];
                snprintf(rp, sizeof rp, "%s/r%d", p, k);
                add_raw((Raw){ strdup(rp), NULL, NULL, T_MEMR, 0 });
            }
            continue;
        }
        int pfd = openat(fd, nm, O_RDONLY | O_DIRECTORY);
        if (pfd < 0) continue;
        Raw r = { strdup(p), NULL, NULL, t, 0 };
        if (t == T_NAND) {
            r.la = read_link(pfd, "a");
            r.lb = read_link(pfd, "b");
            r.init = read_bit(pfd, "init", 0);
        } else if (t == T_DFF) {
            r.la = read_link(pfd, "d");
            r.init = read_bit(pfd, "init", 0);
        } else {
            r.init = read_bit(pfd, "value", 0);
        }
        close(pfd);
        add_raw(r);
    }
    closedir(d);
}

static int rawcmp(const void *x, const void *y) {
    return strcmp(((const Raw *)x)->path, ((const Raw *)y)->path);
}

static void free_net(Net *n) {
    if (!n) return;
    for (int m = 0; m < n->nmems; m++) {
        if (n->mems[m].data) munmap(n->mems[m].data, n->mems[m].size);
        if (n->mems[m].fd >= 0) close(n->mems[m].fd);
    }
    free(n->mems); free(n->reads.v);
    for (int i = 0; i < n->n; i++) free(n->path[i]);
    for (int l = 0; l <= n->maxlvl; l++) free(n->bucket[l].v);
    free(n->path); free(n->type); free(n->val); free(n->init); free(n->ia); free(n->ib);
    free(n->fo_off); free(n->fo); free(n->lvl); free(n->queued); free(n->cand);
    free(n->busy); free(n->htab); free(n->gates.v); free(n->dffs.v);
    free(n->bucket); free(n->candlist.v); free(n);
}

static int wire(Net *n, int i, char *link) {
    int j = link ? resolve(n, n->path[i], link) : -1;
    free(link);
    if (j < 0) { n->nbroken++; return T_GND; }
    return j;
}

/* Combinational nodes (gates and read bits) and their inputs. */
static int comb(Net *n, int g) { return n->type[g] == T_NAND || n->type[g] == T_MEMR; }
static int n_inputs(Net *n, int g) { return n->type[g] == T_NAND ? 2 : n->mems[n->ia[g]].na; }
static int input(Net *n, int g, int k) {
    return n->type[g] == T_NAND ? (k ? n->ib[g] : n->ia[g]) : n->mems[n->ia[g]].a[k];
}

/* Gate depth by depth-first search; a wire back into the current path is
 * feedback (a latch) and does not count. */
static void levelize(Net *n) {
    uint8_t *st = calloc(n->n, 1);
    int *stk = malloc(n->n * sizeof(int)), *k = calloc(n->n, sizeof(int));
    for (int s = 0; s < n->gates.n + n->reads.n; s++) {
        int g0 = s < n->gates.n ? n->gates.v[s] : n->reads.v[s - n->gates.n], sp = 0;
        if (st[g0]) continue;
        st[g0] = 1;
        stk[sp++] = g0;
        while (sp) {
            int g = stk[sp - 1];
            if (k[g] < n_inputs(n, g)) {
                int c = input(n, g, k[g]++);
                if (!comb(n, c)) continue;
                if (st[c] == 1) n->cyclic = 1;
                else if (!st[c]) { st[c] = 1; stk[sp++] = c; }
                continue;
            }
            int l = 0;
            for (int m = 0; m < n_inputs(n, g); m++) {
                int c = input(n, g, m);
                if (comb(n, c) && st[c] == 2 && n->lvl[c] > l) l = n->lvl[c];
            }
            n->lvl[g] = l + 1;
            if (l + 1 > n->maxlvl) n->maxlvl = l + 1;
            st[g] = 2;
            sp--;
        }
    }
    free(st); free(stk); free(k);
}

/* Values written to the q of flip-flops that are not loaded yet (for example
 * while cp -r copies a machine); they are applied by the next load. */
typedef struct { char *path; uint8_t v; } Pending;
static Pending *pending;
static int npending, cappending;

static void add_pending(const char *path, int v) {
    if (npending == cappending)
        pending = realloc(pending, (cappending = cappending ? cappending * 2 : 256) * sizeof *pending);
    pending[npending++] = (Pending){ strdup(path), (uint8_t)v };
}

static char *folder_of(const char *path) {
    return strndup(path, strrchr(path, '/') - path);
}

/* Map X.mem/data. A missing file is an array of size 0: it reads as zeros. */
static void load_mem(Mem *m, int r0) {
    char *dir = folder_of(raw[r0 - 3].path), p[PATH_MAX];
    struct stat st;
    snprintf(p, sizeof p, "%s/data", dir + 1);
    free(dir);
    m->r0 = r0;
    m->fd = openat(bfd, p, O_RDWR);
    if (m->fd < 0 || fstat(m->fd, &st) || st.st_size == 0) return;
    m->data = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, m->fd, 0);
    if (m->data == MAP_FAILED) m->data = NULL;
    else m->size = st.st_size;
}

static Net *load(Net *old) {
    double t0 = now();
    nraw = 0;
    walk("");
    qsort(raw, nraw, sizeof *raw, rawcmp);

    Net *n = calloc(1, sizeof *n);
    int N = n->n = nraw + 3;
    n->path = malloc(N * sizeof(char *));
    n->type = malloc(N); n->val = calloc(N, 1); n->init = calloc(N, 1);
    n->ia = malloc(N * sizeof(int)); n->ib = malloc(N * sizeof(int));
    n->lvl = calloc(N, sizeof(int));
    n->queued = calloc(N, 1); n->cand = calloc(N, 1);
    n->busy = calloc(N, sizeof(uint32_t));
    const char *vn[3] = { "/vcc", "/gnd", "/clk" };
    for (int i = 0; i < 3; i++) {
        n->path[i] = strdup(vn[i]);
        n->type[i] = i;
    }
    n->val[T_VCC] = 1;
    for (int i = 0; i < nraw; i++) {
        n->path[i + 3] = raw[i].path;
        n->type[i + 3] = raw[i].type;
        n->init[i + 3] = raw[i].init;
    }
    for (n->hcap = 16; n->hcap < 2 * N; n->hcap *= 2) {}
    n->htab = malloc(n->hcap * sizeof(int));
    memset(n->htab, -1, n->hcap * sizeof(int));
    for (int i = 0; i < N; i++) {
        uint32_t h = hash(n->path[i]) & (n->hcap - 1);
        while (n->htab[h] >= 0) h = (h + 1) & (n->hcap - 1);
        n->htab[h] = i;
    }

    for (int i = 3; i < N; i++)
        if (raw[i - 3].type == T_MEMR && !strcmp(strrchr(raw[i - 3].path, '/'), "/r0")) n->nmems++;
    n->mems = calloc(n->nmems ? n->nmems : 1, sizeof(Mem));
    for (int i = 0, m = 0; i < N; i++) {
        n->ia[i] = n->ib[i] = T_GND;
        if (i < 3) continue;
        Raw *r = &raw[i - 3];
        if (r->type == T_MEMR) {
            int bit = atoi(strrchr(r->path, '/') + 2);
            if (bit == 0) load_mem(&n->mems[m++], i);
            n->ia[i] = m - 1;
            n->ib[i] = bit;
            ipush(&n->reads, i);
        } else if (r->type == T_NAND) {
            n->ia[i] = wire(n, i, r->la);
            n->ib[i] = wire(n, i, r->lb);
            ipush(&n->gates, i);
        } else if (r->type == T_DFF) {
            n->ia[i] = wire(n, i, r->la);
            ipush(&n->dffs, i);
        } else {
            n->npins++;
        }
        int j = old ? lookup(old, n->path[i]) : -1;
        if (r->type == T_PIN) n->val[i] = n->init[i];
        else n->val[i] = j >= 0 && old->type[j] == r->type ? old->val[j] : n->init[i];
    }
    for (int m = 0; m < n->nmems; m++) {
        Mem *mm = &n->mems[m];
        char *dir = folder_of(n->path[mm->r0]);
        for (int k = 0; k < MEM_LINKS; k++) {
            char nm[16], lp[PATH_MAX];
            mem_link_name(nm, sizeof nm, k);
            snprintf(lp, sizeof lp, "%s/%s", dir + 1, nm);
            char *lk = read_link(bfd, lp);
            if (k < MAX_ADDR_BITS && !lk) { k = MAX_ADDR_BITS - 1; continue; }   /* end of address */
            int j = lk ? resolve(n, dir, lk) : T_GND;
            if (lk && j < 0) { n->nbroken++; j = T_GND; }
            free(lk);
            if (k < MAX_ADDR_BITS) mm->a[mm->na++] = j;
            else if (k < MAX_ADDR_BITS + WORD_BITS) mm->w[k - MAX_ADDR_BITS] = j;
            else mm->we[k - MAX_ADDR_BITS - WORD_BITS] = j;
        }
        free(dir);
    }

    n->fo_off = calloc(N + 1, sizeof(int));
    for (int i = 0; i < N; i++) {
        if (n->type[i] == T_NAND) { n->fo_off[n->ia[i] + 1]++; n->fo_off[n->ib[i] + 1]++; }
        if (n->type[i] == T_DFF) n->fo_off[n->ia[i] + 1]++;
        if (n->type[i] == T_MEMR)
            for (int k = 0; k < n_inputs(n, i); k++) n->fo_off[input(n, i, k) + 1]++;
    }
    for (int i = 0; i < N; i++) n->fo_off[i + 1] += n->fo_off[i];
    n->fo = malloc((n->fo_off[N] + 1) * sizeof(int));
    int *fill = malloc(N * sizeof(int));
    memcpy(fill, n->fo_off, N * sizeof(int));
    for (int i = 0; i < N; i++) {
        if (n->type[i] == T_NAND) { n->fo[fill[n->ia[i]]++] = i; n->fo[fill[n->ib[i]]++] = i; }
        if (n->type[i] == T_DFF) n->fo[fill[n->ia[i]]++] = i;
        if (n->type[i] == T_MEMR)
            for (int k = 0; k < n_inputs(n, i); k++) n->fo[fill[input(n, i, k)]++] = i;
    }
    free(fill);

    levelize(n);
    n->bucket = calloc(n->maxlvl + 1, sizeof(ivec));
    n->lo = INT_MAX;
    n->hi = -1;
    for (int k = 0; k < npending; k++) {
        int i = lookup(n, pending[k].path);
        if (i >= 0 && n->type[i] == T_DFF) n->val[i] = pending[k].v;
        free(pending[k].path);
    }
    npending = 0;
    free_net(old);
    load_ms = (now() - t0) * 1000;
    reloads++;
    return n;
}

/* ---------- evaluation: event-driven ---------- */

static int mem_bit(const Mem *m, uint64_t addr, int bit) {
    uint64_t byte = addr * (WORD_BITS / 8) + bit / 8;
    return byte < m->size ? m->data[byte] >> (bit & 7) & 1 : 0;
}

static uint64_t mem_addr(Net *n, const Mem *m) {
    uint64_t a = 0;
    for (int k = 0; k < m->na; k++) a |= (uint64_t)n->val[m->a[k]] << k;
    return a;
}

static uint8_t eval(Net *n, int g) {
    if (n->type[g] == T_NAND) return !(n->val[n->ia[g]] & n->val[n->ib[g]]);
    const Mem *m = &n->mems[n->ia[g]];
    return mem_bit(m, mem_addr(n, m), n->ib[g]);
}

static void schedule(Net *n, int g) {
    if (n->queued[g]) return;
    n->queued[g] = 1;
    int l = n->lvl[g];
    ipush(&n->bucket[l], g);
    if (l < n->lo) n->lo = l;
    if (l > n->hi) n->hi = l;
}

static void mark(Net *n, int d) {
    if (!n->cand[d]) { n->cand[d] = 1; ipush(&n->candlist, d); }
}

static void changed(Net *n, int i) {
    for (int k = n->fo_off[i]; k < n->fo_off[i + 1]; k++) {
        int f = n->fo[k];
        if (n->type[f] == T_DFF) mark(n, f);
        else schedule(n, f);
    }
}

static void propagate(Net *n) {
    uint64_t limit = 64 * (uint64_t)n->gates.n + 1000, done = 0;
    while (n->lo <= n->hi) {
        int l = n->lo;
        n->lo = l + 1;
        ivec *b = &n->bucket[l];
        while (b->n) {
            int g = b->v[--b->n];
            n->queued[g] = 0;
            uint8_t v = eval(n, g);
            if (profiling) n->busy[g]++;
            if (++done > limit) goto oscillating;
            if (v != n->val[g]) { n->val[g] = v; changed(n, g); }
        }
    }
    evals += done;
    n->lo = INT_MAX;
    n->hi = -1;
    return;
oscillating:
    oscillations++;
    evals += done;
    for (int l = 0; l <= n->maxlvl; l++) {
        for (int k = 0; k < n->bucket[l].n; k++) n->queued[n->bucket[l].v[k]] = 0;
        n->bucket[l].n = 0;
    }
    n->lo = INT_MAX;
    n->hi = -1;
}

static void settle_all(Net *n) {
    for (int k = 0; k < n->gates.n; k++) schedule(n, n->gates.v[k]);
    for (int k = 0; k < n->reads.n; k++) schedule(n, n->reads.v[k]);
    for (int k = 0; k < n->dffs.n; k++) mark(n, n->dffs.v[k]);
    propagate(n);
}

static void set_clk(Net *n, int v) {
    n->val[T_CLK] = v;
    changed(n, T_CLK);
    propagate(n);
}

static void mem_reread(Net *n, const Mem *m) {
    for (int k = 0; k < WORD_BITS; k++) schedule(n, m->r0 + k);
}

/* The bytes a .mem writes on this tick, from its wires' current values. */
static int mem_store(Net *n, Mem *m) {
    int any = 0;
    uint64_t addr = mem_addr(n, m);
    for (int b = 0; b < WORD_BITS / 8; b++) {
        if (!n->val[m->we[b]]) continue;
        uint64_t byte = addr * (WORD_BITS / 8) + b;
        if (byte >= m->size) continue;
        uint8_t v = 0;
        for (int k = 0; k < 8; k++) v |= n->val[m->w[8 * b + k]] << k;
        m->data[byte] = v;
        any = 1;
    }
    return any;
}

static void tick(Net *n) {
    static ivec flip;
    flip.n = 0;
    for (int k = 0; k < n->candlist.n; k++) {
        int d = n->candlist.v[k];
        n->cand[d] = 0;
        if (n->val[n->ia[d]] != n->val[d]) ipush(&flip, d);
    }
    n->candlist.n = 0;
    for (int m = 0; m < n->nmems; m++)
        if (mem_store(n, &n->mems[m])) mem_reread(n, &n->mems[m]);
    for (int k = 0; k < flip.n; k++) {
        n->val[flip.v[k]] ^= 1;
        changed(n, flip.v[k]);
    }
    propagate(n);
    if (n->fo_off[T_CLK + 1] > n->fo_off[T_CLK]) { set_clk(n, 1); set_clk(n, 0); }
}

/* ---------- the machine ---------- */

/* Re-read the tree after structural edits. A big tree is only re-read once
 * the edits have paused (cp -r makes a million of them), unless `force`. */
static void ensure_loaded(int force) {
    if (!dirty) return;
    if (!force && net && load_ms > 50 && now() - last_edit < 0.2) return;
    dirty = 0;
    net = load(net);
    settle_all(net);
}

static void do_reset(void) {
    for (int i = 3; i < net->n; i++)
        if (net->type[i] != T_PIN) net->val[i] = net->init[i];
    net->val[T_CLK] = 0;
    ticks = 0;
    settle_all(net);
}

static int get_bit(int i) { return net->val[i]; }

/* Drive a node from outside: a pin (from its value file) or a flip-flop (fault injection). */
static void set_bit(int i, int v) {
    if (net->val[i] == v) return;
    net->val[i] = v;
    changed(net, i);
    propagate(net);
}

static int write_pin_file(int i, int v) {
    char p[PATH_MAX];
    snprintf(p, sizeof p, "%s/value", net->path[i] + 1);
    int fd = openat(bfd, p, O_WRONLY | O_TRUNC);
    if (fd < 0) return -errno;
    int r = write(fd, v ? "1\n" : "0\n", 2) == 2 ? 0 : -EIO;
    close(fd);
    return r;
}

/* Bits of a bus: the symlinks named 0, 1, 2, ... in its folder. */
static int bus_bits(const char *dir, int *bits) {
    int k;
    for (k = 0; k < 64; k++) {
        char lp[PATH_MAX], lk[PATH_MAX];
        snprintf(lp, sizeof lp, "%s/%d", dir + 1, k);
        ssize_t L = readlinkat(bfd, lp, lk, sizeof lk - 1);
        if (L < 0) break;
        lk[L] = 0;
        bits[k] = resolve(net, dir, lk);
    }
    return k;
}

static unsigned long long bus_read(const char *dir) {
    int bits[64], k = bus_bits(dir, bits);
    unsigned long long v = 0;
    for (int i = 0; i < k; i++)
        if (bits[i] >= 0 && get_bit(bits[i])) v |= 1ULL << i;
    return v;
}

/* Writing a bus drives the pins and sets the flip-flops among its bits;
 * bits that are gate outputs ignore it, like writes to a gate's out. */
static int bus_write(const char *dir, unsigned long long v) {
    int bits[64], k = bus_bits(dir, bits);
    for (int i = 0; i < k; i++) {
        int j = bits[i], b = (v >> i) & 1;
        if (j < 0 || (net->type[j] != T_PIN && net->type[j] != T_DFF) || net->val[j] == b) continue;
        if (net->type[j] == T_PIN) {
            int r = write_pin_file(j, b);
            if (r) return r;
        }
        net->val[j] = b;
        changed(net, j);
    }
    propagate(net);
    return 0;
}

/* ---------- real-time clock ---------- */

static void *runner(void *arg) {
    (void)arg;
    double last = now(), debt = 0, mark_t = last;
    uint64_t mark_ticks = ticks, mark_evals = evals;
    for (;;) {
        double t = now(), hz = run_hz;
        if (t - mark_t >= 1) {
            rate_ticks = (ticks - mark_ticks) / (t - mark_t);
            rate_evals = ticks > mark_ticks ? (double)(evals - mark_evals) / (ticks - mark_ticks) : 0;
            mark_t = t; mark_ticks = ticks; mark_evals = evals;
        }
        if (hz <= 0) { debt = 0; last = t; usleep(5000); continue; }
        debt += (t - last) * hz;
        last = t;
        if (debt > hz * 0.1) debt = hz * 0.1;
        if (debt < 1) { usleep(500); continue; }
        pthread_mutex_lock(&M);
        ensure_loaded(0);
        long want = (long)debt, done = 0;
        while (done < want) {
            tick(net);
            ticks++;
            if ((++done & 15) == 0 && (waiting || now() - t > 0.004)) break;
        }
        pthread_mutex_unlock(&M);
        debt -= done;
        while (waiting) sched_yield();
    }
    return NULL;
}

/* ---------- what a path is ---------- */

enum { V_NONE, V_CTLDIR, V_CONSTDIR, V_CTL, V_OUT, V_Q, V_BUS, V_MEMR };
static const char *ctl_names[] = { "clock", "run", "reset", "reload", "stats", "profile" };
enum { C_CLOCK, C_RUN, C_RESET, C_RELOAD, C_STATS, C_PROFILE, NCTL };

static int is_const(const char *p) {
    return !strcmp(p, "/vcc") || !strcmp(p, "/gnd") || !strcmp(p, "/clk");
}

/* Classify a path; for a computed file, `dir` gets its primitive folder (and
 * for X.mem/rN, `ctl` gets N). */
static int classify(const char *path, char *dir, int *ctl) {
    if (!strcmp(path, "/.ctl")) return V_CTLDIR;
    if (!strncmp(path, "/.ctl/", 6)) {
        for (int i = 0; i < NCTL; i++)
            if (!strcmp(path + 6, ctl_names[i])) { *ctl = i; return V_CTL; }
        return V_NONE;
    }
    if (is_const(path)) return V_CONSTDIR;
    const char *s = strrchr(path, '/');
    if (s == path) return V_NONE;
    size_t L = s - path;
    if (L >= PATH_MAX) return V_NONE;
    memcpy(dir, path, L);
    dir[L] = 0;
    const char *nm = strrchr(dir, '/') + 1;
    int t = is_const(dir) ? T_VCC : prim_type(nm);
    if (!strcmp(s, "/out") && (t == T_NAND || t == T_PIN || t == T_VCC)) return V_OUT;
    if (!strcmp(s, "/q") && t == T_DFF) return V_Q;
    if (!strcmp(s, "/value") && t == T_BUS) return V_BUS;
    if (t == T_MEM && s[1] == 'r' && s[2]) {
        char *e;
        long k = strtol(s + 2, &e, 10);
        if (!*e && k >= 0 && k < WORD_BITS && (s[2] != '0' || !s[3])) { *ctl = k; return V_MEMR; }
    }
    return V_NONE;
}

static int prim_exists(const char *dir) {
    struct stat st;
    return is_const(dir) || (!fstatat(bfd, rel(dir), &st, AT_SYMLINK_NOFOLLOW) && S_ISDIR(st.st_mode));
}

/* Evaluations per folder since profiling started, busiest first:
 * each node counts toward the folder that holds it. */
typedef struct { const char *dir; size_t len; uint64_t n; } Busy;

static int busycmp(const void *x, const void *y) {
    uint64_t a = ((const Busy *)x)->n, b = ((const Busy *)y)->n;
    return a < b ? 1 : a > b ? -1 : 0;
}

static int profile_text(char *buf, size_t sz) {
    Net *n = net;
    Busy *b = calloc(n->n, sizeof *b);
    int nb = 0;
    uint64_t total = 0;
    for (int i = 3; i < n->n; i++) {   /* paths are sorted, so a folder's nodes are adjacent */
        if (!n->busy[i]) continue;
        const char *p = n->path[i];
        size_t len = strrchr(p, '/') - p;
        if (!nb || b[nb - 1].len != len || strncmp(b[nb - 1].dir, p, len)) b[nb++] = (Busy){ p, len, 0 };
        b[nb - 1].n += n->busy[i];
        total += n->busy[i];
    }
    qsort(b, nb, sizeof *b, busycmp);
    int o = snprintf(buf, sz, "%s %llu evaluations\n", profiling ? "on" : "off", (unsigned long long)total);
    for (int k = 0; k < nb && k < 400 && o < (int)sz; k++)
        o += snprintf(buf + o, sz - o, "%12llu %5.1f%% %.*s\n", (unsigned long long)b[k].n,
                      100.0 * b[k].n / total, (int)b[k].len, b[k].dir);
    free(b);
    return o < (int)sz ? o : (int)sz - 1;
}

/* Text of a computed file. Caller holds M. */
static int content(int kind, const char *dir, int ctl, char *buf, size_t sz) {
    ensure_loaded(0);
    if (kind == V_OUT || kind == V_Q) {
        int i = lookup(net, dir);
        return i < 0 ? -ENOENT : snprintf(buf, sz, "%d\n", get_bit(i));
    }
    if (kind == V_BUS) return snprintf(buf, sz, "%llu\n", bus_read(dir));
    if (kind == V_MEMR) {
        char p[PATH_MAX];
        snprintf(p, sizeof p, "%s/r%d", dir, ctl);
        int i = lookup(net, p);
        return i < 0 ? -ENOENT : snprintf(buf, sz, "%d\n", get_bit(i));
    }
    switch (ctl) {
    case C_CLOCK: return snprintf(buf, sz, "%llu\n", (unsigned long long)ticks);
    case C_RUN: return snprintf(buf, sz, "%g\n", run_hz);
    case C_RELOAD: return snprintf(buf, sz, "%llu\n", (unsigned long long)reloads);
    case C_PROFILE: return profile_text(buf, sz);
    case C_STATS:
        return snprintf(buf, sz,
            "nand %d\ndff %d\npin %d\nmem %d\nbroken_wires %d\nlevels %d\nfeedback %s\n"
            "ticks %llu\nrun_hz %g\ntick_rate %.0f\nevals_per_tick %.1f\nevals_total %llu\n"
            "oscillations %llu\nreloads %llu\nload_ms %.1f\n",
            net->gates.n, net->dffs.n, net->npins, net->nmems, net->nbroken,
            net->maxlvl, net->cyclic ? "yes" : "no", (unsigned long long)ticks, run_hz,
            rate_ticks, rate_evals, (unsigned long long)evals,
            (unsigned long long)oscillations, (unsigned long long)reloads, load_ms);
    }
    return 0;
}

/* Handle a write to a computed file. Caller holds M. */
static int command(int kind, const char *dir, int ctl, const char *buf) {
    ensure_loaded(kind == V_CTL && ctl != C_RUN);
    if (kind == V_OUT) {
        int i = lookup(net, dir);
        if (i >= 0 && net->type[i] == T_PIN) {
            int v = buf[0] == '1', r = write_pin_file(i, v);
            if (!r) set_bit(i, v);
            return r;
        }
        return 0;   /* writes to a gate's out are ignored, so cp -r works */
    }
    if (kind == V_MEMR) return 0;
    if (kind == V_Q) {
        int i = lookup(net, dir);
        if (i < 0) add_pending(dir, buf[0] == '1');
        else set_bit(i, buf[0] == '1');
        return 0;
    }
    if (kind == V_BUS) return bus_write(dir, strtoull(buf, NULL, 0));
    switch (ctl) {
    case C_CLOCK:
        for (long k = strtol(buf, NULL, 0); k > 0; k--, ticks++) tick(net);
        return 0;
    case C_RUN: run_hz = strtod(buf, NULL); return 0;
    case C_RESET: do_reset(); return 0;
    case C_RELOAD: dirty = 1; ensure_loaded(1); return 0;
    case C_PROFILE:   /* 1: clear and start counting, 0: stop */
        profiling = buf[0] == '1';
        if (profiling) memset(net->busy, 0, net->n * sizeof *net->busy);
        return 0;
    }
    return -EPERM;
}

/* ---------- FUSE operations ---------- */

static int structural(int r) {
    if (r == 0) {
        last_edit = now();
        dirty = 1;
    }
    return r;
}

static int ok(int r) { return r < 0 ? -errno : 0; }

static int nf_getattr(const char *path, struct stat *st, struct fuse_file_info *fi) {
    (void)fi;
    char dir[PATH_MAX], buf[65536];
    int ctl = 0, kind = classify(path, dir, &ctl);
    memset(st, 0, sizeof *st);
    st->st_uid = getuid();
    st->st_gid = getgid();
    if (kind == V_CTLDIR || kind == V_CONSTDIR) {
        st->st_mode = S_IFDIR | 0755;
        st->st_nlink = 2;
        return 0;
    }
    if (kind == V_NONE) return ok(fstatat(bfd, rel(path), st, AT_SYMLINK_NOFOLLOW));
    if (kind != V_CTL && !prim_exists(dir)) return -ENOENT;
    st->st_mode = S_IFREG | 0644;
    st->st_nlink = 1;
    lock();
    int n = content(kind, dir, ctl, buf, sizeof buf);
    unlock();
    if (n < 0) return n;
    st->st_size = n;
    return 0;
}

static int nf_readdir(const char *path, void *buf, fuse_fill_dir_t fill, off_t off,
                      struct fuse_file_info *fi, enum fuse_readdir_flags fl) {
    (void)off; (void)fi; (void)fl;
    char dir[PATH_MAX];
    int ctl = -1, kind = classify(path, dir, &ctl);
    fill(buf, ".", NULL, 0, 0);
    fill(buf, "..", NULL, 0, 0);
    if (kind == V_CTLDIR) {
        for (int i = 0; i < NCTL; i++) fill(buf, ctl_names[i], NULL, 0, 0);
        return 0;
    }
    if (kind == V_CONSTDIR) { fill(buf, "out", NULL, 0, 0); return 0; }
    int fd = openat(bfd, rel(path), O_RDONLY | O_DIRECTORY);
    if (fd < 0) return -errno;
    DIR *d = fdopendir(fd);
    struct dirent *e;
    while ((e = readdir(d)))
        if (strcmp(e->d_name, ".") && strcmp(e->d_name, ".."))
            fill(buf, e->d_name, NULL, 0, 0);
    closedir(d);
    if (!strcmp(path, "/")) {
        fill(buf, ".ctl", NULL, 0, 0);
        fill(buf, "vcc", NULL, 0, 0);
        fill(buf, "gnd", NULL, 0, 0);
        fill(buf, "clk", NULL, 0, 0);
    }
    switch (prim_type(strrchr(path, '/') + 1)) {
    case T_NAND: case T_PIN: fill(buf, "out", NULL, 0, 0); break;
    case T_DFF: fill(buf, "q", NULL, 0, 0); break;
    case T_BUS: fill(buf, "value", NULL, 0, 0); break;
    case T_MEM:
        for (int k = 0; k < WORD_BITS; k++) {
            char nm[8];
            snprintf(nm, sizeof nm, "r%d", k);
            fill(buf, nm, NULL, 0, 0);
        }
        break;
    }
    return 0;
}

static int is_pin_value(const char *path) {
    const char *s = strrchr(path, '/');
    if (strcmp(s, "/value")) return 0;
    const char *d = s - 1;
    while (d > path && *d != '/') d--;
    char nm[NAME_MAX + 1];
    snprintf(nm, sizeof nm, "%.*s", (int)(s - d - 1), d + 1);
    return prim_type(nm) == T_PIN;
}

static int is_init(const char *path) { return !strcmp(strrchr(path, '/'), "/init"); }

/* X.mem/data: the file behind a .mem. */
static int is_mem_data(const char *path) {
    const char *s = strrchr(path, '/');
    if (strcmp(s, "/data")) return 0;
    const char *d = s - 1;
    while (d > path && *d != '/') d--;
    char nm[NAME_MAX + 1];
    snprintf(nm, sizeof nm, "%.*s", (int)(s - d - 1), d + 1);
    return prim_type(nm) == T_MEM;
}

/* After X.mem/data was written: its read bits may have changed. A new size
 * means mapping it again, which a reload does. */
static void mem_data_written(const char *path) {
    char p[PATH_MAX];
    snprintf(p, sizeof p, "%.*s/r0", (int)(strrchr(path, '/') - path), path);
    lock();
    ensure_loaded(0);
    int i = dirty || !net ? -1 : lookup(net, p);
    if (i >= 0 && net->type[i] == T_MEMR) {
        Mem *m = &net->mems[net->ia[i]];
        struct stat st;
        if (m->fd < 0 || fstat(m->fd, &st) || (size_t)st.st_size != m->size) dirty = 1;
        else { mem_reread(net, m); propagate(net); }
    } else {
        dirty = 1;
    }
    unlock();
}

/* A new init value takes effect at the next reset. If the folder is already
 * loaded there is nothing to re-read, which keeps loading a program quick. */
static void set_init(const char *path, int v) {
    char dir[PATH_MAX];
    snprintf(dir, sizeof dir, "%.*s", (int)(strrchr(path, '/') - path), path);
    lock();
    int i = dirty || !net ? -1 : lookup(net, dir);
    if (i >= 0 && (net->type[i] == T_DFF || net->type[i] == T_NAND)) net->init[i] = v;
    else dirty = 1;
    unlock();
}

/* An open file: a real file in the backing tree (fd), or a computed one whose
 * text is captured on the first read, so that a value which changes between
 * two read() calls still reads as one consistent number. */
typedef struct { int fd, len; char *text; } Handle;

static Handle *handle(struct fuse_file_info *fi) { return (Handle *)(uintptr_t)fi->fh; }

static int open_common(const char *path, struct fuse_file_info *fi, int create, mode_t mode) {
    char dir[PATH_MAX];
    int ctl = -1, kind = classify(path, dir, &ctl), fd = -1;
    if (kind != V_NONE) {
        if (kind != V_CTL && !prim_exists(dir)) return -ENOENT;
        fi->direct_io = 1;
    } else {
        fd = create ? openat(bfd, rel(path), fi->flags | O_CREAT, mode)
                    : openat(bfd, rel(path), fi->flags);
        if (fd < 0) return -errno;
        /* The daemon changes a .mem's data file behind the kernel's back
         * (through its own mapping), so the kernel must not cache it; Linux
         * drops the cache on each open, macOS does not. */
        if (is_mem_data(path)) fi->direct_io = 1;
    }
    Handle *h = calloc(1, sizeof *h);
    h->fd = fd;
    fi->fh = (uintptr_t)h;
    if (create && (is_init(path) || is_pin_value(path) || is_mem_data(path))) dirty = 1;
    return 0;
}

static int nf_open(const char *path, struct fuse_file_info *fi) { return open_common(path, fi, 0, 0); }

static int nf_create(const char *path, mode_t mode, struct fuse_file_info *fi) {
    return open_common(path, fi, 1, mode);
}

static int nf_read(const char *path, char *buf, size_t sz, off_t off, struct fuse_file_info *fi) {
    Handle *h = handle(fi);
    if (h->fd >= 0) {
        ssize_t r = pread(h->fd, buf, sz, off);
        return r < 0 ? -errno : r;
    }
    if (!h->text) {
        char dir[PATH_MAX], tmp[65536];
        int ctl = -1, kind = classify(path, dir, &ctl);
        lock();
        int n = content(kind, dir, ctl, tmp, sizeof tmp);
        unlock();
        if (n < 0) return n;
        if (n >= (int)sizeof tmp) n = sizeof tmp - 1;
        h->text = malloc(n);
        memcpy(h->text, tmp, n);
        h->len = n;
    }
    if (off >= h->len) return 0;
    if ((size_t)(h->len - off) < sz) sz = h->len - off;
    memcpy(buf, h->text + off, sz);
    return sz;
}

static int nf_write(const char *path, const char *buf, size_t sz, off_t off,
                    struct fuse_file_info *fi) {
    Handle *h = handle(fi);
    if (h->fd >= 0) {
        ssize_t r = pwrite(h->fd, buf, sz, off);
        if (r < 0) return -errno;
        if (is_init(path)) set_init(path, buf[0] == '1');
        if (is_mem_data(path)) mem_data_written(path);
        if (is_pin_value(path)) {
            lock();
            ensure_loaded(0);
            char dir[PATH_MAX];
            snprintf(dir, sizeof dir, "%.*s", (int)(strrchr(path, '/') - path), path);
            int i = lookup(net, dir);
            if (i >= 0) set_bit(i, buf[0] == '1');
            unlock();
        }
        return r;
    }
    char dir[PATH_MAX], tmp[256];
    int ctl = -1, kind = classify(path, dir, &ctl);
    snprintf(tmp, sizeof tmp, "%.*s", (int)(sz < sizeof tmp - 1 ? sz : sizeof tmp - 1), buf);
    lock();
    int r = command(kind, dir, ctl, tmp);
    unlock();
    return r < 0 ? r : (int)sz;
}

static int nf_release(const char *path, struct fuse_file_info *fi) {
    (void)path;
    Handle *h = handle(fi);
    if (h->fd >= 0) close(h->fd);
    free(h->text);
    free(h);
    return 0;
}

static int nf_truncate(const char *path, off_t size, struct fuse_file_info *fi) {
    char dir[PATH_MAX];
    int ctl = -1;
    if (classify(path, dir, &ctl) != V_NONE) return 0;
    int r;
    if (fi && fi->fh && handle(fi)->fd >= 0) {
        r = ok(ftruncate(handle(fi)->fd, size));
    } else {
        int fd = openat(bfd, rel(path), O_WRONLY);
        if (fd < 0) return -errno;
        r = ok(ftruncate(fd, size));
        close(fd);
    }
    if (!r && is_mem_data(path)) mem_data_written(path);
    return r;
}

static int nf_readlink(const char *path, char *buf, size_t sz) {
    ssize_t r = readlinkat(bfd, rel(path), buf, sz - 1);
    if (r < 0) return -errno;
    buf[r] = 0;
    return 0;
}

static int nf_mkdir(const char *path, mode_t mode) { return structural(ok(mkdirat(bfd, rel(path), mode))); }
static int nf_rmdir(const char *path) { return structural(ok(unlinkat(bfd, rel(path), AT_REMOVEDIR))); }
static int nf_symlink(const char *target, const char *path) {
    return structural(ok(symlinkat(target, bfd, rel(path))));
}
static int nf_link(const char *from, const char *to) {
    return structural(ok(linkat(bfd, rel(from), bfd, rel(to), 0)));
}

static int nf_unlink(const char *path) {
    char dir[PATH_MAX];
    int ctl = -1;
    if (classify(path, dir, &ctl) != V_NONE) return 0;   /* lets rm -r remove a gate */
    return structural(ok(unlinkat(bfd, rel(path), 0)));
}

static int nf_rename(const char *from, const char *to, unsigned int flags) {
    if (flags) return -EINVAL;
    return structural(ok(renameat(bfd, rel(from), bfd, rel(to))));
}

static int nf_chmod(const char *path, mode_t mode, struct fuse_file_info *fi) {
    (void)fi;
    char dir[PATH_MAX];
    int ctl = -1;
    if (classify(path, dir, &ctl) != V_NONE) return 0;
    return ok(fchmodat(bfd, rel(path), mode, 0));
}

static int nf_chown(const char *path, uid_t u, gid_t g, struct fuse_file_info *fi) {
    (void)fi;
    char dir[PATH_MAX];
    int ctl = -1;
    if (classify(path, dir, &ctl) != V_NONE) return 0;
    return ok(fchownat(bfd, rel(path), u, g, AT_SYMLINK_NOFOLLOW));
}

static int nf_utimens(const char *path, const struct timespec tv[2], struct fuse_file_info *fi) {
    (void)fi;
    char dir[PATH_MAX];
    int ctl = -1;
    if (classify(path, dir, &ctl) != V_NONE) return 0;
    return ok(utimensat(bfd, rel(path), tv, AT_SYMLINK_NOFOLLOW));
}

static int nf_statfs(const char *path, struct statvfs *st) {
    (void)path;
    return ok(fstatvfs(bfd, st));
}

static void *nf_init(struct fuse_conn_info *conn, struct fuse_config *cfg) {
    (void)conn;
    cfg->entry_timeout = 0;
    cfg->attr_timeout = 0;
    cfg->negative_timeout = 0;
    pthread_t t;
    pthread_create(&t, NULL, runner, NULL);
    pthread_detach(t);
    return NULL;
}

static const struct fuse_operations ops = {
    .init = nf_init, .getattr = nf_getattr, .readdir = nf_readdir, .open = nf_open,
    .create = nf_create, .read = nf_read, .write = nf_write, .release = nf_release,
    .truncate = nf_truncate, .readlink = nf_readlink, .mkdir = nf_mkdir, .rmdir = nf_rmdir,
    .symlink = nf_symlink, .link = nf_link, .unlink = nf_unlink, .rename = nf_rename,
    .chmod = nf_chmod, .chown = nf_chown, .utimens = nf_utimens, .statfs = nf_statfs,
};

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: nandfs BACKING_DIR MOUNTPOINT [fuse options]\n");
        return 2;
    }
    bfd = open(argv[1], O_RDONLY | O_DIRECTORY);
    if (bfd < 0) { perror(argv[1]); return 1; }
    argv[1] = argv[0];
    return fuse_main(argc - 1, argv + 1, &ops, NULL);
}
