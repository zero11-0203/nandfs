#!/usr/bin/env python3
"""Read the screen rows over and over while the machine runs flat out; every
read must be one well-formed number (a computed file's text must not change
between the read() calls that make up one read of it).

    read_race.py MOUNT ROM [SECONDS]
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "viewer"))
from play import Machine, load_program  # noqa: E402

mc = Machine(sys.argv[1])
load_program(mc, sys.argv[2])
mc.run(1_000_000)
bad = reads = 0
t0 = time.time()
try:
    while time.time() - t0 < float(sys.argv[3] if len(sys.argv) > 3 else 10):
        for k in range(32):
            text = (mc.m / f"display/r{k}/px").read_text()
            reads += 1
            if not (text.endswith("\n") and text[:-1].isdigit()):
                bad += 1
                print("bad read:", repr(text))
finally:
    mc.run(0)
print(f"{reads} reads, {bad} malformed")
sys.exit(1 if bad else 0)
