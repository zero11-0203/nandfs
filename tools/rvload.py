#!/usr/bin/env python3
"""Load a program into the mounted RV32IM folder computer and reset it.

    rvload.py MOUNT RAM.bin [ROM.rom]

Writes RAM.bin at the start of rv32/ram.mem/data and zeros over the rest
(and the same for the ROM), then resets the flip-flops. The data files keep
their size: a .mem's size is its address space.
"""
import sys
from pathlib import Path


def fill(path, image):
    size = path.stat().st_size
    if len(image) > size:
        sys.exit(f"{path}: image of {len(image)} bytes does not fit in {size}")
    with open(path, "r+b") as f:
        f.write(image)
        zeros = bytes(1 << 20)
        left = size - len(image)
        while left:
            n = min(left, len(zeros))
            f.write(zeros[:n])
            left -= n


def load(mount, ram, rom=None):
    m = Path(mount)
    fill(m / "rv32/ram.mem/data", Path(ram).read_bytes())
    fill(m / "rv32/rom.mem/data", Path(rom).read_bytes() if rom else b"")
    (m / ".ctl/reset").write_text("1\n")


if __name__ == "__main__":
    load(*sys.argv[1:4])
