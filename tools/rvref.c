/* rvref: reference model of the RV32IM folder computer (hw/rv32/, a PicoRV32
 * CPU). The gate machine must match it instruction for instruction.
 *
 *   rvref [options] RAM.bin [ROM.bin]
 *     -n N          stop after N instructions (default: run until halt)
 *     -t            trace: one line per instruction (see below)
 *     -c            print the console log as the program writes it
 *     -f DIR        write each completed frame to DIR/frameNNNNN.ppm
 *     -s            print a summary at the end
 *     -p FILE       write an instruction count per pc to FILE (profile)
 *
 * Memory map
 *   0x00000000  RAM, 16 MB (the RAM .mem: RAM.bin is loaded at address 0)
 *   0x10000000  ROM, 8 MB, read-only (the ROM .mem: the DOOM WAD)
 *   0x20000000  TIME: instruction fetches since reset / 1000 (read-only)
 *   0x20000004  KEYS: one bit per key pin (read-only)
 *   elsewhere   reads as 0; writes are ignored
 *
 * Software conventions (not hardware): the framebuffer is 320x200 8-bit
 * pixels at FB_ADDR with a palette of 256 0x00RRGGBB words at PALETTE_ADDR,
 * FRAME_ADDR counts finished frames, and CONSOLE_ADDR holds a byte count
 * followed by the console text.
 *
 * TIME counts the CPU's instruction fetches, a counter built of gates.
 * PicoRV32 fetches each instruction once, plus the word after a taken
 * branch (fetched before the branch resolves, then dropped), and it has
 * already fetched the next instruction when a load reads TIME. (The machine
 * has no clock a program could see; this one ticks with the program, so
 * every machine that runs it reads the same values.)
 *
 * ECALL, EBREAK, an illegal instruction or a misaligned access halts the
 * machine. FENCE is a no-op; FENCE.I (Zifencei) is not implemented.
 *
 * Trace line: "instret pc insn rd=value" or "... [addr]=value/mask" for stores.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define RAM_BITS 24
#define ROM_BITS 23
#define RAM_SIZE (1u << RAM_BITS)
#define ROM_SIZE (1u << ROM_BITS)
#define ROM_BASE 0x10000000u
#define IO_BASE 0x20000000u
#define FETCHES_PER_MS 1000u

#define FB_ADDR 0x00E00000u
#define PALETTE_ADDR 0x00E10000u
#define FRAME_ADDR 0x00DFFFF0u
#define CONSOLE_ADDR 0x00F00000u

static uint8_t *ram, *rom;
static uint32_t x[32], pc, keys;
static uint64_t instret, wasted_fetches;
static uint32_t *profile;
static const char *halt_reason;

static int load(uint32_t a, int size, uint32_t *v) {
    if (a & (size - 1)) return -1;
    const uint8_t *p;
    if (a < RAM_SIZE) p = ram + a;
    else if (a - ROM_BASE < ROM_SIZE) p = rom + (a - ROM_BASE);
    else if ((a & ~7u) == IO_BASE) {
        uint32_t fetches = instret + 2 + wasted_fetches;   /* this load and the next */
        uint32_t w = a & 4 ? keys : fetches / FETCHES_PER_MS;
        w >>= 8 * (a & 3);
        *v = size == 4 ? w : size == 2 ? w & 0xffff : w & 0xff;
        return 0;
    }
    else { *v = 0; return 0; }   /* unmapped reads as zero */
    *v = size == 1 ? p[0] : size == 2 ? (uint32_t)(p[0] | p[1] << 8)
                                      : (uint32_t)(p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24);
    return 0;
}

static int store(uint32_t a, int size, uint32_t v) {
    if (a & (size - 1)) return -1;
    if (a >= RAM_SIZE) return 0;   /* ROM and I/O ignore writes */
    for (int i = 0; i < size; i++) ram[a + i] = v >> (8 * i);
    return 0;
}

static int32_t sx(uint32_t v, int bits) { return (int32_t)(v << (32 - bits)) >> (32 - bits); }

/* Execute one instruction. Returns 0, or -1 if the machine halted. */
static int step(FILE *trace) {
    uint32_t insn;
    if (pc & 3 || load(pc, 4, &insn)) { halt_reason = "misaligned pc"; return -1; }
    if (profile && pc < RAM_SIZE) profile[pc >> 2]++;
    uint32_t op = insn & 0x7f, rd = insn >> 7 & 31, f3 = insn >> 12 & 7;
    uint32_t a = x[insn >> 15 & 31], b = x[insn >> 20 & 31], f7 = insn >> 25;
    int32_t imm_i = sx(insn >> 20, 12);
    int32_t imm_s = sx((insn >> 25) << 5 | (insn >> 7 & 31), 12);
    int32_t imm_b = sx((insn >> 31) << 12 | (insn >> 7 & 1) << 11 | (insn >> 25 & 63) << 5 | (insn >> 8 & 15) << 1, 13);
    int32_t imm_j = sx((insn >> 31) << 20 | (insn >> 12 & 255) << 12 | (insn >> 20 & 1) << 11 | (insn >> 21 & 1023) << 1, 21);
    uint32_t next = pc + 4, val = 0;
    int wb = 1, st_size = 0;
    uint32_t st_addr = 0;

    switch (op) {
    case 0x37: val = insn & 0xfffff000; break;                         /* LUI */
    case 0x17: val = pc + (insn & 0xfffff000); break;                  /* AUIPC */
    case 0x6f: val = pc + 4; next = pc + imm_j; break;                 /* JAL */
    case 0x67: val = pc + 4; next = (a + imm_i) & ~1u; break;          /* JALR */
    case 0x63: {                                                       /* branches */
        int t;
        switch (f3) {
        case 0: t = a == b; break;
        case 1: t = a != b; break;
        case 4: t = (int32_t)a < (int32_t)b; break;
        case 5: t = (int32_t)a >= (int32_t)b; break;
        case 6: t = a < b; break;
        case 7: t = a >= b; break;
        default: halt_reason = "illegal branch"; return -1;
        }
        if (t) { next = pc + imm_b; wasted_fetches++; }
        wb = 0;
        break;
    }
    case 0x03: {                                                       /* loads */
        static const int size[8] = { 1, 2, 4, 0, 1, 2, 0, 0 };
        if (!size[f3]) { halt_reason = "illegal load"; return -1; }
        if (load(a + imm_i, size[f3], &val)) { halt_reason = "misaligned load"; return -1; }
        if (f3 == 0) val = sx(val, 8);
        if (f3 == 1) val = sx(val, 16);
        break;
    }
    case 0x23:                                                         /* stores */
        if (f3 > 2) { halt_reason = "illegal store"; return -1; }
        st_size = 1 << f3;
        st_addr = a + imm_s;
        if (store(st_addr, st_size, b)) { halt_reason = "misaligned store"; return -1; }
        wb = 0;
        break;
    case 0x13: {                                                       /* ALU immediate */
        uint32_t sh = imm_i & 31;
        switch (f3) {
        case 0: val = a + imm_i; break;
        case 1: if (f7) goto illegal; val = a << sh; break;
        case 2: val = (int32_t)a < imm_i; break;
        case 3: val = a < (uint32_t)imm_i; break;
        case 4: val = a ^ imm_i; break;
        case 5:
            if (f7 == 0x20) val = (int32_t)a >> sh;
            else if (f7 == 0) val = a >> sh;
            else goto illegal;
            break;
        case 6: val = a | imm_i; break;
        case 7: val = a & imm_i; break;
        }
        break;
    }
    case 0x33:                                                         /* ALU register */
        if (f7 == 1) {
            int64_t sa = (int32_t)a, sb = (int32_t)b;
            switch (f3) {
            case 0: val = a * b; break;
            case 1: val = (uint32_t)((sa * sb) >> 32); break;
            case 2: val = (uint32_t)((sa * (int64_t)(uint64_t)b) >> 32); break;
            case 3: val = (uint32_t)(((uint64_t)a * b) >> 32); break;
            case 4: val = b == 0 ? 0xffffffff : (a == 0x80000000 && b == 0xffffffff) ? a : (uint32_t)((int32_t)a / (int32_t)b); break;
            case 5: val = b == 0 ? 0xffffffff : a / b; break;
            case 6: val = b == 0 ? a : (a == 0x80000000 && b == 0xffffffff) ? 0 : (uint32_t)((int32_t)a % (int32_t)b); break;
            case 7: val = b == 0 ? a : a % b; break;
            }
        } else if (f7 == 0 || (f7 == 0x20 && (f3 == 0 || f3 == 5))) {
            switch (f3) {
            case 0: val = f7 ? a - b : a + b; break;
            case 1: val = a << (b & 31); break;
            case 2: val = (int32_t)a < (int32_t)b; break;
            case 3: val = a < b; break;
            case 4: val = a ^ b; break;
            case 5: val = f7 ? (uint32_t)((int32_t)a >> (b & 31)) : a >> (b & 31); break;
            case 6: val = a | b; break;
            case 7: val = a & b; break;
            }
        } else goto illegal;
        break;
    case 0x0f:                                                         /* FENCE */
        if (f3) goto illegal;                                          /* no FENCE.I */
        wb = 0;
        break;
    case 0x73: halt_reason = (insn >> 20) == 1 ? "ebreak" : "ecall"; return -1;
    default:
    illegal:
        halt_reason = "illegal instruction";
        return -1;
    }
    instret++;
    if (wb && rd) x[rd] = val;
    if (trace) {
        if (st_size)
            fprintf(trace, "%llu %08x %08x [%08x]=%08x/%d\n", (unsigned long long)instret, pc, insn,
                    st_addr, st_size == 4 ? b : b & ((1u << (8 * st_size)) - 1), st_size);
        else if (wb && rd)
            fprintf(trace, "%llu %08x %08x x%d=%08x\n", (unsigned long long)instret, pc, insn, rd, val);
        else
            fprintf(trace, "%llu %08x %08x\n", (unsigned long long)instret, pc, insn);
    }
    pc = next;
    return 0;
}

static uint32_t ram32(uint32_t a) { uint32_t v; load(a, 4, &v); return v; }

static void write_frame(const char *dir, uint32_t n) {
    char name[4096];
    snprintf(name, sizeof name, "%s/frame%05u.ppm", dir, n);
    FILE *f = fopen(name, "wb");
    if (!f) { perror(name); return; }
    fprintf(f, "P6\n320 200\n255\n");
    for (int i = 0; i < 320 * 200; i++) {
        uint32_t p = ram32(PALETTE_ADDR + 4 * ram[FB_ADDR + i]);
        uint8_t rgb[3] = { p >> 16, p >> 8, p };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
}

static void load_file(const char *path, uint8_t *dst, size_t max) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    size_t n = fread(dst, 1, max, f);
    if (!feof(f) && fgetc(f) != EOF) { fprintf(stderr, "%s: larger than %zu bytes\n", path, max); exit(1); }
    fclose(f);
    (void)n;
}

int main(int argc, char **argv) {
    long long limit = -1;
    int tr = 0, console = 0, summary = 0, c;
    const char *frames = NULL, *prof = NULL;
    while ((c = getopt(argc, argv, "n:tcf:sp:")) != -1) {
        if (c == 'n') limit = atoll(optarg);
        else if (c == 't') tr = 1;
        else if (c == 'c') console = 1;
        else if (c == 'f') frames = optarg;
        else if (c == 's') summary = 1;
        else if (c == 'p') prof = optarg;
        else return 2;
    }
    if (optind >= argc) {
        fprintf(stderr, "usage: rvref [-n N] [-t] [-c] [-f DIR] [-s] [-p FILE] RAM.bin [ROM.bin]\n");
        return 2;
    }
    if (prof) profile = calloc(RAM_SIZE / 4, sizeof *profile);
    ram = calloc(1, RAM_SIZE);
    rom = calloc(1, ROM_SIZE);
    load_file(argv[optind], ram, RAM_SIZE);
    if (optind + 1 < argc) load_file(argv[optind + 1], rom, ROM_SIZE);

    uint32_t shown = 0, frame = 0;
    uint64_t frame_instret = 0;
    while (limit < 0 || (long long)instret < limit) {
        if (step(tr ? stdout : NULL)) break;
        if ((instret & 1023) == 0) {
            if (console) {
                uint32_t len = ram32(CONSOLE_ADDR);
                for (; shown < len && shown < (1u << 20); shown++) putchar(ram[CONSOLE_ADDR + 4 + shown]);
                fflush(stdout);
            }
            uint32_t f = ram32(FRAME_ADDR);
            if (f != frame) {
                if (summary)
                    fprintf(stderr, "frame %u at %llu instructions (+%llu)\n", f,
                            (unsigned long long)instret, (unsigned long long)(instret - frame_instret));
                frame_instret = instret;
                frame = f;
                if (frames) write_frame(frames, f);
            }
        }
    }
    if (console) {
        uint32_t len = ram32(CONSOLE_ADDR);
        for (; shown < len && shown < (1u << 20); shown++) putchar(ram[CONSOLE_ADDR + 4 + shown]);
    }
    if (prof) {
        FILE *f = fopen(prof, "w");
        if (!f) { perror(prof); return 1; }
        for (uint32_t i = 0; i < RAM_SIZE / 4; i++)
            if (profile[i]) fprintf(f, "%08x %u\n", i * 4, profile[i]);
        fclose(f);
    }
    if (summary || halt_reason) {
        fprintf(stderr, "%s after %llu instructions; pc=%08x gp=%u a0=%u\n",
                halt_reason ? halt_reason : "stopped", (unsigned long long)instret, pc, x[3], x[10]);
    }
    return halt_reason && strcmp(halt_reason, "ecall") && strcmp(halt_reason, "ebreak") ? 1 : 0;
}
