#!/usr/bin/env python3
"""Run DOOM on the mounted RV32IM folder computer and save every frame.

    rvdoom.py MOUNT OUTDIR --ram doom.bin --rom doom1.rom [--ref DIR] [--chunk N]
    rvdoom.py MOUNT OUTDIR --resume [--ref DIR]

The runner only reads and writes files. It clocks the machine in chunks
(.ctl/clock); after each chunk it reads the frame counter the program keeps
in RAM (rv32/ram.mem/data); when the counter moves it reads the 320x200 frame
and its palette from the same file and writes OUTDIR/frames/frameNNNNN.ppm.

  --ref DIR   compare each frame with DIR/frameNNNNN.ppm from tools/rvref.c -f
              (the frames must be identical, byte for byte)

Every --checkpoint frames it saves the machine: the RAM file and the value of
every flip-flop (read through their q files). --resume writes them back and
carries on, so a run that takes days survives a restart. The console text
the program prints goes to OUTDIR/console.txt, progress to OUTDIR/log.txt.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from rvload import fill, load  # noqa: E402

FB, PALETTE, FRAME, CONSOLE = 0xE00000, 0xE10000, 0xDFFFF0, 0xF00000
W, H = 320, 200


class Machine:
    def __init__(self, mount):
        self.m = Path(mount)
        self.ram = self.m / "rv32/ram.mem/data"
        self.backing_dffs = None

    def clock(self, n):
        (self.m / ".ctl/clock").write_text(f"{n}\n")

    def read(self, addr, n):
        with open(self.ram, "rb") as f:
            f.seek(addr)
            return f.read(n)

    def u32(self, addr):
        return int.from_bytes(self.read(addr, 4), "little")

    def num(self, path):
        return int((self.m / path).read_text())

    def frame_ppm(self):
        pix = self.read(FB, W * H)
        pal = self.read(PALETTE, 1024)
        rgb = [bytes((pal[4 * i + 2], pal[4 * i + 1], pal[4 * i])) for i in range(256)]
        return b"P6\n320 200\n255\n" + b"".join(rgb[p] for p in pix)

    def dffs(self):
        """Every flip-flop folder under rv32/, as paths relative to the mount."""
        out = []
        for root, dirs, _ in os.walk(self.m / "rv32"):
            for d in dirs:
                if d.endswith(".dff"):
                    out.append(os.path.relpath(os.path.join(root, d), self.m))
            dirs[:] = [d for d in dirs if not d.endswith((".dff", ".nand", ".mem", ".bus", ".pin"))]
        return sorted(out)


def checkpoint(mc, out, state):
    ck = out / "checkpoint.tmp"
    ck.mkdir(exist_ok=True)
    with open(mc.ram, "rb") as f, open(ck / "ram.bin", "wb") as g:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            g.write(b)
    bits = {p: (mc.m / p / "q").read_text().strip() for p in mc.dffs()}
    (ck / "dffs.json").write_text(json.dumps(bits))
    (ck / "state.json").write_text(json.dumps(state))
    old = out / "checkpoint"
    if old.exists():
        for f in old.iterdir():
            f.unlink()
        old.rmdir()
    ck.rename(old)


def restore(mc, out, rom):
    ck = out / "checkpoint"
    fill(mc.m / "rv32/rom.mem/data", Path(rom).read_bytes())
    fill(mc.ram, (ck / "ram.bin").read_bytes())
    (mc.m / ".ctl/reset").write_text("1\n")
    for p, v in json.loads((ck / "dffs.json").read_text()).items():
        (mc.m / p / "q").write_text(v + "\n")
    return json.loads((ck / "state.json").read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mount")
    ap.add_argument("out")
    ap.add_argument("--ram")
    ap.add_argument("--rom")
    ap.add_argument("--ref")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--chunk", type=int, default=200000, help="ticks per step")
    ap.add_argument("--checkpoint", type=int, default=50, help="frames between checkpoints")
    ap.add_argument("--frames", type=int, help="stop after this frame")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    mc = Machine(a.mount)
    if a.resume:
        state = json.loads((out / "checkpoint/state.json").read_text())
        state = restore(mc, out, state["rom"])
        print(f"resumed at frame {state['frame']}, {state['ticks']} ticks", flush=True)
    else:
        load(a.mount, a.ram, a.rom)
        state = {"ticks": 0, "frame": 0, "console": 0, "seconds": 0.0, "rom": str(Path(a.rom).resolve()),
                 "mismatches": 0}
    log = open(out / "log.txt", "a")
    console = open(out / "console.txt", "a")
    t_start, sec0 = time.time(), state["seconds"]
    while True:
        mc.clock(a.chunk)
        state["ticks"] += a.chunk
        state["seconds"] = sec0 + time.time() - t_start
        n = mc.u32(CONSOLE)
        if n > state["console"]:
            text = mc.read(CONSOLE + 4 + state["console"], n - state["console"]).decode(errors="replace")
            console.write(text)
            console.flush()
            sys.stdout.write(text)
            state["console"] = n
        f = mc.u32(FRAME)
        halted = mc.num("rv32/halted")
        if f != state["frame"]:
            if f != state["frame"] + 1:
                print(f"warning: frame counter jumped from {state['frame']} to {f}", flush=True)
            state["frame"] = f
            ppm = mc.frame_ppm()
            (out / "frames" / f"frame{f:05d}.ppm").write_bytes(ppm)
            match = ""
            if a.ref:
                ref = Path(a.ref) / f"frame{f:05d}.ppm"
                same = ref.exists() and ref.read_bytes() == ppm
                state["mismatches"] += not same
                match = " =ref" if same else " DIFFERS FROM REFERENCE"
            instret = mc.num("rv32/instret")
            line = (f"frame {f} at {state['ticks']} ticks, {instret} instruction fetches, "
                    f"{state['seconds'] / 3600:.2f} h{match}")
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()
            if f % a.checkpoint == 0:
                checkpoint(mc, out, state)
            if a.frames and f >= a.frames:
                break
        if halted:
            print("the machine halted", flush=True)
            break
    log.close()
    if a.ref:
        print(f"{state['mismatches']} frames differed from the reference")


if __name__ == "__main__":
    main()
