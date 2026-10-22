#!/usr/bin/env python3
"""Run programs on rv32.v (Icarus) and on tools/rvref.c and compare them
instruction by instruction: pc, instruction, and the register or memory
written. Then compare how each run ended: halted, instruction count, a0.

    rv_lockstep_verilog.py SIM RVREF PROGRAM.bin...
"""
import re
import subprocess
import sys


def run(sim, rvref, prog):
    v = subprocess.run(["vvp", "-n", sim, f"+ram={prog}"], capture_output=True, text=True).stdout
    r = subprocess.run([rvref, "-t", "-s", prog], capture_output=True, text=True)
    vlines = [l for l in v.splitlines() if l[:1].isdigit()]
    vend = next(l for l in v.splitlines() if l.startswith("halted="))
    m = re.search(r"halted=(\d+) after (\d+) instructions, (\d+) cycles; pc=(\w+) a0=(\d+)", vend)
    vsum = (m.group(1) == "1", int(m.group(2)), int(m.group(5)))
    cycles = int(m.group(3))
    m = re.search(r"(\w[\w ]*) after (\d+) instructions; pc=(\w+) gp=\d+ a0=(\d+)", r.stderr)
    rsum = (m.group(1) != "stopped", int(m.group(2)), int(m.group(4)))
    rlines = r.stdout.splitlines()
    for k, (a, b) in enumerate(zip(vlines, rlines)):
        if a != b:
            return f"instruction {k + 1}: verilog '{a}' reference '{b}'"
    if len(vlines) != len(rlines):
        return f"verilog ran {len(vlines)} instructions, reference {len(rlines)}"
    if vsum != rsum:
        return f"end: verilog {vsum} reference {rsum} (halted, instructions, a0)"
    return None, rsum + (cycles,)


def main():
    sim, rvref, progs = sys.argv[1], sys.argv[2], sys.argv[3:]
    bad = 0
    for p in progs:
        res = run(sim, rvref, p)
        name = p.rsplit("/", 1)[-1]
        if isinstance(res, str):
            bad += 1
            print(f"FAIL {name}: {res}")
        else:
            _, (halted, n, a0, cycles) = res
            print(f"ok   {name}: {n} instructions, {cycles} cycles, a0={a0}")
    print(f"{len(progs) - bad}/{len(progs)} match")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
