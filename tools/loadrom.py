#!/usr/bin/env python3
"""Load a CHIP-8 program into the folder machine's RAM, then reset it.

    loadrom.py MOUNT/chip8 ROM.ch8 [--poke ADDR=BYTE ...] [--no-reset]

Each RAM bit is a flip-flop; this writes the init file of every bit whose
value changes (the equivalent of flashing memory) and then writes .ctl/reset,
which loads every flip-flop from its init file. Byte A lives in
memory/ram/hX/hY/hZ, where X, Y and Z are the hex digits of A.
"""
import argparse
import sys
from pathlib import Path


def byte_dir(machine, a):
    return machine / "memory" / "ram" / f"h{a >> 8:x}" / f"h{a >> 4 & 15:x}" / f"h{a & 15:x}"


def load(machine, image, reset=True):
    machine = Path(machine)
    written = 0
    for a in range(4096):
        d = byte_dir(machine, a)
        for bit in range(8):
            f = d / f"q_{bit}.dff" / "init"
            want = "1" if image[a] >> bit & 1 else "0"
            if f.read_text()[:1] != want:
                f.write_text(want + "\n")
                written += 1
    if reset:
        (machine.parent / ".ctl" / "reset").write_text("1\n")
    return written


def image_for(rom, pokes=()):
    image = bytearray(4096)
    image[0x200:0x200 + len(rom)] = rom
    for a, b in pokes:
        image[a] = b
    return image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("machine")
    ap.add_argument("rom")
    ap.add_argument("--poke", action="append", default=[])
    ap.add_argument("--no-reset", action="store_true")
    a = ap.parse_args()
    pokes = [tuple(int(x, 0) for x in p.split("=")) for p in a.poke]
    n = load(a.machine, image_for(Path(a.rom).read_bytes(), pokes), not a.no_reset)
    print(f"{n} bits changed", file=sys.stderr)


if __name__ == "__main__":
    main()
