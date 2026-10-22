#!/usr/bin/env python3
"""Compare two machine traces line by line and report the first difference.

    tracecmp.py A.trace B.trace

Lines are "slot pc v0..vf i sp dt st" (hex), as written by chip8ref.py, the
Verilog testbench and the folder-machine runner.
"""
import sys

FIELDS = ["slot", "pc"] + [f"v{k:x}" for k in range(16)] + ["i", "sp", "dt", "st"]


def compare(a, b, names=("A", "B")):
    """Returns None if equal, else a description of the first difference."""
    for n, (x, y) in enumerate(zip(a, b)):
        if x.split() != y.split():
            fx, fy = x.split(), y.split()
            diff = [f"{f}: {u} vs {v}" for f, u, v in zip(FIELDS, fx, fy) if u != v]
            return (f"line {n + 1} differs ({', '.join(diff)})\n"
                    f"  {names[0]}: {x}\n  {names[1]}: {y}\n"
                    f"  previous: {a[n - 1] if n else '(start)'}")
    if len(a) != len(b):
        return f"lengths differ: {names[0]} has {len(a)} lines, {names[1]} has {len(b)}"
    return None


if __name__ == "__main__":
    a = open(sys.argv[1]).read().splitlines()
    b = open(sys.argv[2]).read().splitlines()
    msg = compare(a, b, sys.argv[1:3])
    print(msg or f"identical ({len(a)} lines)")
    sys.exit(1 if msg else 0)
