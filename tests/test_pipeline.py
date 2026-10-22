#!/usr/bin/env python3
"""hw/test/counter.v, synthesized by Yosys and turned into folders, must
match the Verilog's behavior.

    test_pipeline.py MOUNTPOINT   (the folder machine is MOUNTPOINT/top)
"""
import random
import sys
from pathlib import Path

T = Path(sys.argv[1]) / "top"
C = Path(sys.argv[1]) / ".ctl"
failures = 0


def rd(p):
    return int((T / p).read_text())


def wr(p, v):
    (T / p).write_text(f"{v}\n")


def check(cond, msg):
    global failures
    if not cond:
        failures += 1
        print("FAIL", msg)


def run(steps, seed):
    for p in ("a", "b", "en", "rst"):
        wr(p, 0)
    (C / "reset").write_text("1")
    rng = random.Random(seed)
    count, trace = 3, []           # `initial count = 3` in the Verilog
    for _ in range(steps):
        a, b = rng.randrange(256), rng.randrange(256)
        en, rst = rng.random() < 0.8, rng.random() < 0.05
        for p, v in (("a", a), ("b", b), ("en", int(en)), ("rst", int(rst))):
            wr(p, v)
        check(rd("sum") == a + b, f"sum {a}+{b} = {rd('sum')}")
        (C / "clock").write_text("1")
        count = 0 if rst else (count + 1) & 255 if en else count
        got = rd("count")
        check(got == count, f"count {got}, expected {count}")
        trace.append(got)
    return trace


run(600, 7)
print("ok" if not failures else f"{failures} failures")
sys.exit(1 if failures else 0)
