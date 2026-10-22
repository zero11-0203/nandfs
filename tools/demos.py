#!/usr/bin/env python3
"""Generate the Phase 1 demo circuits as folders.

    demos.py OUTDIR

  xor/       one XOR from four NANDs, inputs a.pin and b.pin
  fa/        a nine-NAND full adder
  adder8/    an 8-bit ripple-carry adder: echo 5 > in_a; echo 7 > in_b; cat sum
  dff/       a flip-flop built from NAND gates next to a primitive flip-flop,
             both fed by the same pin, plus a 4-bit shift register of each
  mem/       a .mem of 16 words (64-byte data file): address, write data and
             byte enables from pins (the address through two NANDs each), and
             a 32-flip-flop register that loads the word read each tick
"""
import shutil
import sys

from circuit import GND, Tree


def build(out):
    shutil.rmtree(out, ignore_errors=True)
    t = Tree(out)

    a, b = t.pin("xor/a"), t.pin("xor/b")
    t.port("xor/out", t.xor("xor/x", a, b))

    a, b, c = t.pin("fa/a"), t.pin("fa/b"), t.pin("fa/cin")
    s, co = t.full_adder("fa/cell", a, b, c)
    t.port("fa/sum", s)
    t.port("fa/cout", co)

    A = [t.pin(f"adder8/a/{i}") for i in range(8)]
    B = [t.pin(f"adder8/b/{i}") for i in range(8)]
    carry, S = GND, []
    for i in range(8):
        s, carry = t.full_adder(f"adder8/fa{i}", A[i], B[i], carry)
        S.append(s)
    t.port("adder8/in_a", t.bus("adder8/in_a", A))
    t.port("adder8/in_b", t.bus("adder8/in_b", B))
    t.port("adder8/sum", t.bus("adder8/sum", S + [carry]))

    d = t.pin("dff/d")
    t.port("dff/q_nand", t.nand_dff("dff/gates", d))
    t.port("dff/q_prim", t.dff("dff/prim", d))
    sig_n = sig_p = d
    qn, qp = [], []
    for i in range(4):
        sig_n = t.nand_dff(f"dff/shift_nand/s{i}", sig_n)
        sig_p = t.dff(f"dff/shift_prim/s{i}", sig_p)
        qn.append(sig_n)
        qp.append(sig_p)
    t.port("dff/shift_nand/value", t.bus("dff/shift_nand/q", qn))
    t.port("dff/shift_prim/value", t.bus("dff/shift_prim/q", qp))

    A = [t.not_(f"mem/abuf/n{i}", t.not_(f"mem/abuf/{i}", t.pin(f"mem/a/{i}"))) for i in range(4)]
    W = [t.pin(f"mem/w/{i}") for i in range(32)]
    WE = [t.pin(f"mem/en/{i}") for i in range(4)]
    m = t.mem("mem/m", A, W, WE, size=64)
    t.port("mem/addr", t.bus("mem/addr", [f"mem/a/{i}.pin/out" for i in range(4)]))
    t.port("mem/wdata", t.bus("mem/wdata", W))
    t.port("mem/we", t.bus("mem/we", WE))
    t.port("mem/rdata", t.bus("mem/rdata", m))
    t.port("mem/reg", t.bus("mem/regq", [t.dff(f"mem/r/q{i}", m[i]) for i in range(32)]))
    print(f"{out}: {t.nands} NAND gates, {t.dffs} flip-flops")


if __name__ == "__main__":
    build(sys.argv[1])
