#!/usr/bin/env python3
"""Check the gate demos (tools/demos.py) through a mounted tree.

    test_gates.py MOUNTPOINT

Truth tables are exhaustive (including the 8-bit adder). The flip-flop built
from NAND gates must match the primitive flip-flop on every tick, and the .mem
must match a model of its words.
"""
import random
import sys
from pathlib import Path

M = Path(sys.argv[1])
failures = 0


def rd(p):
    return int((M / p).read_text())


def wr(p, v):
    (M / p).write_text(f"{v}\n")


def check(cond, msg):
    global failures
    if not cond:
        failures += 1
        print("FAIL", msg)


def truth_tables(full_adder8):
    for a in (0, 1):
        for b in (0, 1):
            wr("xor/a.pin/value", a)
            wr("xor/b.pin/value", b)
            check(rd("xor/out") == a ^ b, f"xor {a} {b}")
            for c in (0, 1):
                wr("fa/a.pin/value", a)
                wr("fa/b.pin/value", b)
                wr("fa/cin.pin/value", c)
                check(rd("fa/sum") == (a + b + c) & 1, f"fa sum {a}{b}{c}")
                check(rd("fa/cout") == (a + b + c) >> 1, f"fa cout {a}{b}{c}")
    pairs = ((a, b) for a in range(256) for b in range(256)) if full_adder8 else \
        [(random.randrange(256), random.randrange(256)) for _ in range(200)]
    for a, b in pairs:
        wr("adder8/in_a", a)
        wr("adder8/in_b", b)
        check(rd("adder8/sum") == a + b, f"adder8 {a}+{b}")


def flipflops(seed, n):
    rng = random.Random(seed)
    wr(".ctl/reset", 1)
    trace = []
    for _ in range(n):
        wr("dff/d.pin/value", rng.randrange(2))
        wr(".ctl/clock", 1)
        row = (rd("dff/q_nand"), rd("dff/q_prim"),
               rd("dff/shift_nand/value"), rd("dff/shift_prim/value"))
        check(row[0] == row[1] and row[2] == row[3], f"nand vs primitive flip-flop {row}")
        trace.append(row)
    return trace


def mem_test(seed, n):
    """Random writes and reads of the 16-word .mem against a model, plus a
    write to its data file from outside."""
    rng = random.Random(seed)
    data = M / "mem/m.mem/data"
    data.write_bytes(bytes(64))
    model = [0] * 16
    trace = []
    for _ in range(n):
        a, w, we = rng.randrange(16), rng.getrandbits(32), rng.choice([0, 0, 15, 1, 2, 4, 8, 5, 3])
        wr("mem/addr", a)
        wr("mem/wdata", w)
        wr("mem/we", we)
        check(rd("mem/rdata") == model[a], f"mem read before tick at {a}")
        check(rd(f"mem/m.mem/r{rng.randrange(32)}") in (0, 1), "mem read bit file")
        wr(".ctl/clock", 1)
        for b in range(4):
            if we >> b & 1:
                model[a] = model[a] & ~(255 << 8 * b) | w & (255 << 8 * b)
        # the register loaded the word as it was before the write
        r = rd("mem/reg")
        got = rd("mem/rdata")
        check(got == model[a], f"mem read after tick at {a}: {got:x} != {model[a]:x}")
        trace.append((r, got))
    check(data.read_bytes() == b"".join(v.to_bytes(4, "little") for v in model), "mem data file")
    wr("mem/we", 0)
    raw = bytearray(data.read_bytes())
    raw[4 * 3: 4 * 4] = (0xDEADBEEF).to_bytes(4, "little")
    with open(data, "r+b") as f:
        f.seek(12)
        f.write(raw[12:16])
    wr("mem/addr", 3)
    check(rd("mem/rdata") == 0xDEADBEEF, "mem sees a write to its data file")
    return trace


truth_tables(full_adder8=True)
mem_test(2, 150)
flipflops(1, 200)
print("ok" if not failures else f"{failures} failures")
sys.exit(1 if failures else 0)
