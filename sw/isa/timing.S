// TIME counts instruction fetches. Read it after every kind of control
// transfer (call, return, indirect jump, taken and untaken branches, loads,
// stores, multiply and divide) so the reference must model PicoRV32's
// fetches exactly. Ends with ECALL; a0 = the sum of every value read.
    .text
    .globl _start
_start:
    li s0, 0x20000000
    li a0, 0
    li s1, 700
loop:
    lw t0, 0(s0)
    add a0, a0, t0
    jal ra, f                // call, return by jalr
    lw t0, 0(s0)
    add a0, a0, t0
    andi t1, s1, 1
    beqz t1, even            // taken half the time
    lw t0, 0(s0)
    add a0, a0, t0
even:
    la t2, next
    jr t2                    // indirect jump
next:
    sw a0, 256(zero)
    lw t0, 0(s0)
    add a0, a0, t0
    addi s1, s1, -1
    bnez s1, loop
    ecall
f:
    lw t0, 0(s0)
    add a0, a0, t0
    mul t1, t0, s1
    div t1, t1, s1
    add a0, a0, t1
    ret
