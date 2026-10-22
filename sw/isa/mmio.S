// The parts of the machine riscv-tests do not cover: TIME (which counts
// instruction fetches), KEYS, byte and halfword loads
// from I/O, reads of unmapped addresses, and writes to ROM and to nowhere.
// Ends with ECALL; a0 = a checksum of everything read.
    .text
    .globl _start
_start:
    li s0, 0x20000000        // TIME
    li s1, 0x10000000        // ROM
    li s2, 0x30000000        // unmapped
    li a0, 0
    li t1, 250
1:  lw t0, 0(s0)
    add a0, a0, t0
    mul t2, t0, t1
    divu t2, t2, t1
    add a0, a0, t2
    addi t1, t1, -1
    bnez t1, 1b
    lb t0, 0(s0)
    add a0, a0, t0
    lhu t0, 2(s0)
    add a0, a0, t0
    lbu t0, 1(s0)
    add a0, a0, t0
    lw t0, 4(s0)             // KEYS
    add a0, a0, t0
    sw a0, 0(s1)             // writes to ROM are ignored
    lw t0, 0(s1)
    add a0, a0, t0
    sw a0, 0(s2)             // and so are writes to unmapped space
    lw t0, 0(s2)
    add a0, a0, t0
    lw t0, 8(s0)             // past the I/O registers
    add a0, a0, t0
    ecall
