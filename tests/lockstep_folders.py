#!/usr/bin/env python3
"""Run the suite (tests/suite.txt) on the folder machine and require
the same trace and final screen as the reference emulator.

    lockstep_folders.py MOUNT [NAME ...]

The machine is MOUNT/chip8. For each slot the runner sets
the keypad pins, advances the clock 32 ticks through .ctl/clock, and reads the
retired-instruction counter; when it moves, it reads the CPU state the way
anyone could: cat cpu/pc, cat cpu/regs/v3/q, ...
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import chip8ref  # noqa: E402
from loadrom import image_for, load  # noqa: E402
from lockstep_verilog import keys_for, load as load_prog, screen_text, suite  # noqa: E402
from tracecmp import compare  # noqa: E402

SLOT_TICKS = 32


class Machine:
    def __init__(self, mount):
        self.mount = Path(mount)
        self.m = self.mount / "chip8"
        self.ctl = self.mount / ".ctl"

    def rd(self, p):
        return int((self.m / p).read_text())

    def state(self):
        cpu = "cpu/"
        v = [self.rd(f"{cpu}regs/v{k:x}/q") for k in range(16)]
        return (self.rd(cpu + "pc"), *v, self.rd(cpu + "i"), self.rd(cpu + "sp"),
                self.rd(cpu + "timers/dt"), self.rd(cpu + "timers/st"))

    def screen(self):
        rows = [self.rd(f"display/r{k}/px") for k in range(32)]
        return ["".join("#" if r >> c & 1 else "." for c in range(64)) for r in rows]

    def run(self, image, slots, keys):
        load(self.m, image)
        (self.m / "keys").write_text("0\n")
        ev, trace, count = list(keys), [], self.rd("icount")
        clock = self.ctl / "clock"
        for s in range(slots):
            while ev and ev[0][0] <= s:
                (self.m / "keys").write_text(f"{ev.pop(0)[1]}\n")
            clock.write_text(f"{SLOT_TICKS}\n")
            c = self.rd("icount")
            if c != count:
                if c != (count + 1) & 0xFFFF:
                    raise SystemExit(f"slot {s}: {c - count} instructions retired in one slot")
                count = c
                trace.append("%d " % s + " ".join("%x" % x for x in self.state()))
        return trace


def main():
    mount = sys.argv[1]
    mc = Machine(mount)
    ok = True
    for prog, slots, pokes in suite(sys.argv[2:]):
        rom, keys = load_prog(prog), keys_for(prog)
        ref_m, ref = chip8ref.run(rom, slots, keys, poke=pokes)
        t0 = time.time()
        got = mc.run(image_for(rom, pokes), slots, keys)
        dt = time.time() - t0
        msg = compare(ref, got, ("ref", "folders"))
        if not msg and mc.screen() != screen_text(ref_m):
            msg = "final screens differ"
        print(f"{prog.name:24} {len(ref):6} instructions  {dt:6.1f}s  " + ("ok" if not msg else "FAIL"))
        if msg:
            print(msg)
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
