// Test environment for riscv-tests (isa/rv32ui, isa/rv32um) on the RV32IM
// folder computer: code from address 0, pass = ECALL with a0 = 0, fail =
// ECALL with a0 = the failing test's number.
#ifndef RISCV_TEST_H
#define RISCV_TEST_H

#define RVTEST_RV32U .macro init; .endm
#define RVTEST_RV64U RVTEST_RV32U
#define TESTNUM gp

#define RVTEST_CODE_BEGIN .text; .globl _start; _start: li TESTNUM, 0;
#define RVTEST_CODE_END unimp
#define RVTEST_PASS li a0, 0; ecall;
#define RVTEST_FAIL mv a0, TESTNUM; ecall;
#define RVTEST_DATA_BEGIN .data; .balign 16;
#define RVTEST_DATA_END

#endif
