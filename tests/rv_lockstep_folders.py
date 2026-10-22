#!/usr/bin/env python3
"""Run programs on the mounted RV32IM folder computer in lockstep with
tools/rvref.c, reading everything through files. The machine is clocked one
tick at a time. PicoRV32 loads the address of each instruction it starts
into its register reg_pc (rv32/cpu/reg_pc) on the same clock edge that
writes back the previous instruction's result; so once reg_pc holds the
address of instruction k+1, instruction k is done, and the register it wrote
(rv32/cpu/cpuregs_N) or the bytes it stored (rv32/ram.mem/data) must match
the reference. At the end the machine must have halted (trapped).

    rv_lockstep_folders.py MOUNT RVREF PROGRAM.bin...
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from rvload import load  # noqa: E402

RAM_SIZE = 16 << 20
MAX_TICKS = 200       # per instruction (a divide takes about 40)


def check(mount, rvref, prog):
    m = Path(mount)
    rd = lambda p: int((m / p).read_text())  # noqa: E731
    clock = m / ".ctl/clock"
    load(mount, prog)
    r = subprocess.run([rvref, "-t", "-s", prog], capture_output=True, text=True)
    trace = r.stdout.splitlines()
    final_pc = int(r.stderr.split("pc=")[1].split()[0], 16)
    data = m / "rv32/ram.mem/data"
    pcs = [int(line.split()[1], 16) for line in trace] + [final_pc]
    for k, line in enumerate(trace):
        f = line.split()
        n, pc = int(f[0]), int(f[1], 16)
        for _ in range(MAX_TICKS):
            clock.write_text("1\n")
            if rd("rv32/cpu/reg_pc") == pcs[k + 1] or rd("rv32/halted"):
                break
        else:
            return f"instruction {n} at {pc:08x} did not finish"
        if len(f) > 3 and f[3].startswith("x"):
            reg, v = f[3][1:].split("=")
            got = rd(f"rv32/cpu/cpuregs_{reg}")
            if got != int(v, 16):
                return f"instruction {n} at {pc:08x}: x{reg}={got:08x}, reference {v}"
        elif len(f) > 3 and int(f[3][1:9], 16) < RAM_SIZE:   # stores elsewhere are ignored
            a, rest = f[3][1:].split("]=")
            v, size = rest.split("/")
            with open(data, "rb") as fh:
                fh.seek(int(a, 16))
                got = int.from_bytes(fh.read(int(size)), "little")
            if got != int(v, 16):
                return f"instruction {n} at {pc:08x}: stored {got:x}, reference {v}"
    clock.write_text(f"{MAX_TICKS}\n")
    if rd("rv32/halted") != 1:
        return "did not halt"
    if rd("rv32/cpu/reg_pc") != final_pc:
        return f"halted at {rd('rv32/cpu/reg_pc'):08x}, reference {final_pc:08x}"
    return None, len(trace)


def main():
    mount, rvref, progs = sys.argv[1], sys.argv[2], sys.argv[3:]
    bad = 0
    for p in progs:
        t0 = time.time()
        res = check(mount, rvref, p)
        name = p.rsplit("/", 1)[-1]
        if isinstance(res, str):
            bad += 1
            print(f"FAIL {name}: {res}", flush=True)
        else:
            print(f"ok   {name}: {res[1]} instructions ({time.time() - t0:.1f}s)", flush=True)
    print(f"{len(progs) - bad}/{len(progs)} match")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
