/* Runtime for picolibc on the RV32IM folder computer: console output in RAM,
 * a read-only file system holding the ROM, and exit by ECALL. */
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "machine.h"
#include "rom.h"

static int console_putc(char c, FILE *f) {
    (void)f;
    uint32_t n = MACHINE_CONSOLE[0];
    if (n < MACHINE_CONSOLE_MAX) {
        ((volatile char *)(MACHINE_CONSOLE + 1))[n] = c;
        MACHINE_CONSOLE[0] = n + 1;
    }
    return (unsigned char)c;
}

static FILE console = FDEV_SETUP_STREAM(console_putc, NULL, NULL, _FDEV_SETUP_WRITE);
FILE *const stdin = &console;
FILE *const stdout = &console;
FILE *const stderr = &console;

void _exit(int status) {
    register int a0 __asm__("a0") = status;
    for (;;) __asm__ volatile("ecall" : : "r"(a0));
}

/* The ROM holds one file. Its name and size are in a 64-byte header:
 * "ROMFILE\0", size (4 bytes little endian), name (NUL-terminated). */
#define ROM_HEADER 64
#define MAX_FD 8
static struct { int open; uint32_t pos; } fds[MAX_FD];

static uint32_t rom_size(void) {
    if (memcmp(MACHINE_ROM, "ROMFILE", 8)) return 0;
    const uint8_t *p = MACHINE_ROM + 8;
    return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24;
}

const unsigned char *rom_file(const char *name, unsigned int *size) {
    *size = rom_size();
    if (!*size || (name && strcmp(name, (const char *)MACHINE_ROM + 12))) return NULL;
    return MACHINE_ROM + ROM_HEADER;
}

/* Word-at-a-time versions; picolibc's copy a byte at a time. GCC must not
 * turn their loops back into calls to themselves. */
#define NO_LOOP_CALLS __attribute__((optimize("no-tree-loop-distribute-patterns")))
NO_LOOP_CALLS void *memcpy(void *restrict dst, const void *restrict src, size_t n) {
    uint8_t *d = dst;
    const uint8_t *s = src;
    if ((((uintptr_t)d ^ (uintptr_t)s) & 3) == 0) {
        for (; n && ((uintptr_t)d & 3); n--) *d++ = *s++;
        for (; n >= 16; n -= 16, d += 16, s += 16) {
            uint32_t a = ((const uint32_t *)s)[0], b = ((const uint32_t *)s)[1];
            uint32_t c = ((const uint32_t *)s)[2], e = ((const uint32_t *)s)[3];
            ((uint32_t *)d)[0] = a; ((uint32_t *)d)[1] = b;
            ((uint32_t *)d)[2] = c; ((uint32_t *)d)[3] = e;
        }
        for (; n >= 4; n -= 4, d += 4, s += 4) *(uint32_t *)d = *(const uint32_t *)s;
    }
    for (; n; n--) *d++ = *s++;
    return dst;
}

NO_LOOP_CALLS void *memset(void *dst, int c, size_t n) {
    uint8_t *d = dst;
    uint32_t w = (uint8_t)c * 0x01010101u;
    for (; n && ((uintptr_t)d & 3); n--) *d++ = c;
    for (; n >= 16; n -= 16, d += 16) {
        ((uint32_t *)d)[0] = w; ((uint32_t *)d)[1] = w;
        ((uint32_t *)d)[2] = w; ((uint32_t *)d)[3] = w;
    }
    for (; n >= 4; n -= 4, d += 4) *(uint32_t *)d = w;
    for (; n; n--) *d++ = c;
    return dst;
}

int open(const char *path, int flags, ...) {
    const char *base = strrchr(path, '/');
    base = base ? base + 1 : path;
    if ((flags & O_ACCMODE) != O_RDONLY || !rom_size() ||
        strcmp(base, (const char *)MACHINE_ROM + 12)) {
        errno = ENOENT;
        return -1;
    }
    for (int fd = 3; fd < MAX_FD; fd++)
        if (!fds[fd].open) {
            fds[fd].open = 1;
            fds[fd].pos = 0;
            return fd;
        }
    errno = EMFILE;
    return -1;
}

int close(int fd) {
    if (fd < 3 || fd >= MAX_FD || !fds[fd].open) { errno = EBADF; return -1; }
    fds[fd].open = 0;
    return 0;
}

ssize_t read(int fd, void *buf, size_t n) {
    if (fd < 3 || fd >= MAX_FD || !fds[fd].open) { errno = EBADF; return -1; }
    uint32_t size = rom_size();
    if (fds[fd].pos >= size) return 0;
    if (n > size - fds[fd].pos) n = size - fds[fd].pos;
    memcpy(buf, MACHINE_ROM + ROM_HEADER + fds[fd].pos, n);
    fds[fd].pos += n;
    return n;
}

ssize_t write(int fd, const void *buf, size_t n) {
    if (fd != 1 && fd != 2) { errno = EBADF; return -1; }
    for (size_t i = 0; i < n; i++) console_putc(((const char *)buf)[i], NULL);
    return n;
}

off_t lseek(int fd, off_t off, int whence) {
    if (fd < 3 || fd >= MAX_FD || !fds[fd].open) { errno = EBADF; return -1; }
    off_t base = whence == SEEK_SET ? 0 : whence == SEEK_CUR ? (off_t)fds[fd].pos : (off_t)rom_size();
    if (base + off < 0) { errno = EINVAL; return -1; }
    fds[fd].pos = base + off;
    return fds[fd].pos;
}

int fstat(int fd, struct stat *st) {
    if (fd < 3 || fd >= MAX_FD || !fds[fd].open) { errno = EBADF; return -1; }
    memset(st, 0, sizeof *st);
    st->st_mode = S_IFREG | 0444;
    st->st_size = rom_size();
    return 0;
}

int stat(const char *path, struct stat *st) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    fstat(fd, st);
    close(fd);
    return 0;
}

int isatty(int fd) { return fd < 3; }
int unlink(const char *path) { (void)path; errno = EROFS; return -1; }
int mkdir(const char *path, mode_t mode) { (void)path; (void)mode; errno = EROFS; return -1; }
int rename(const char *from, const char *to) { (void)from; (void)to; errno = EROFS; return -1; }
