#!/usr/bin/env python3
"""Play the folder computer in a terminal.

    play.py MOUNT [ROM.ch8|PROGRAM.asm] [--hz 23040] [--record out.gif]
    play.py MOUNT ROM --frames 300 --dump      (no terminal; print the screen)

The viewer only reads and writes files: it loads the ROM into the RAM
flip-flops' init files, writes the clock rate to .ctl/run, reads the 32
display rows (chip8/display/rN/px, each a bus over 64 pixel flip-flops), and
writes the keypad pins (chip8/keys). Keys, as on most CHIP-8 emulators:

    1 2 3 4        1 2 3 C
    q w e r   ->   4 5 6 D
    a s d f        7 8 9 E
    z x c v        A 0 B F        Esc quits.

Terminals report key presses but not releases, so a key counts as held for a
short time after each press (key repeat keeps it held while you hold it).
"""
import argparse
import os
import select
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import c8asm  # noqa: E402
from loadrom import image_for, load  # noqa: E402

KEYMAP = {c: k for c, k in zip("1234qwerasdfzxcv",
                                [1, 2, 3, 12, 4, 5, 6, 13, 7, 8, 9, 14, 10, 0, 11, 15])}
HOLD = 0.3
MASTER_HZ = 23040


class Machine:
    def __init__(self, mount):
        self.mount = Path(mount)
        self.m = self.mount / "chip8"
        self.ctl = self.mount / ".ctl"

    def rd(self, p):
        return int((self.m / p).read_text())

    def rows(self):
        return [self.rd(f"display/r{k}/px") for k in range(32)]

    def stats(self):
        out = {}
        for line in (self.ctl / "stats").read_text().splitlines():
            k, v = line.split(" ", 1)
            out[k] = v
        return out

    def set_keys(self, mask):
        (self.m / "keys").write_text(f"{mask}\n")

    def run(self, hz):
        (self.ctl / "run").write_text(f"{hz}\n")


def render(rows, status):
    """64x32 pixels as 64x16 characters, two pixel rows per character."""
    top = "\x1b[H\x1b[2m┌" + "─" * 64 + "┐\x1b[0m\r\n"
    lines = [top]
    for y in range(0, 32, 2):
        a, b = rows[y], rows[y + 1]
        s = "".join(" ▀▄█"[(a >> c & 1) | (b >> c & 1) << 1] for c in range(64))
        lines.append("\x1b[2m│\x1b[0m" + s + "\x1b[2m│\x1b[0m\r\n")
    lines.append("\x1b[2m└" + "─" * 64 + "┘\x1b[0m\r\n")
    lines.append(status.ljust(66)[:66] + "\x1b[K\r\n")
    return "".join(lines)


def load_program(mc, path):
    path = Path(path)
    rom = c8asm.assemble(path.read_text()) if path.suffix == ".asm" else path.read_bytes()
    mc.run(0)
    load(mc.m, image_for(rom))


class Recorder:
    """Collects frames and writes them as a GIF through ffmpeg."""

    def __init__(self, path, fps=30):
        self.path, self.fps, self.frames = path, fps, []

    def add(self, rows):
        self.frames.append(bytes(255 if r >> c & 1 else 0 for r in rows for c in range(64)))

    def save(self):
        if not self.frames:
            return
        scale = "scale=512:256:flags=neighbor"
        p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
             "-s", "64x32", "-r", str(self.fps), "-i", "-",
             "-vf", f"{scale},split[a][b];[a]palettegen=max_colors=2[p];[b][p]paletteuse",
             self.path], stdin=subprocess.PIPE)
        p.communicate(b"".join(self.frames))


def play(mc, hz, record):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    held = {}
    mask_sent = -1
    rec = Recorder(record) if record else None
    last_ic, last_t, ips = mc.rd("icount"), time.time(), 0.0
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        mc.run(hz)
        frame = 0
        while True:
            t0 = time.time()
            while select.select([fd], [], [], 0)[0]:
                ch = os.read(fd, 1).decode(errors="ignore").lower()
                if ch == "\x1b":
                    return
                if ch in KEYMAP:
                    held[KEYMAP[ch]] = t0 + HOLD
            mask = sum(1 << k for k, until in held.items() if until > t0)
            if mask != mask_sent:
                mc.set_keys(mask)
                mask_sent = mask
            rows = mc.rows()
            if rec:
                rec.add(rows)
            if frame % 15 == 0:
                st = mc.stats()
                ic, now = mc.rd("icount"), time.time()
                ips = ((ic - last_ic) & 0xFFFF) / (now - last_t)
                last_ic, last_t = ic, now
                beep = "♪" if mc.rd("buzzer") else " "
                status = (f" {float(st['tick_rate']) / 1000:5.1f} kHz  {ips:4.0f} instr/s  "
                          f"{float(st['evals_per_tick']):6.0f} gates/tick  {beep}  Esc quits")
            sys.stdout.write(render(rows, status))
            sys.stdout.flush()
            frame += 1
            time.sleep(max(0, 1 / 30 - (time.time() - t0)))
    finally:
        mc.run(0)
        mc.set_keys(0)
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if rec:
            rec.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mount")
    ap.add_argument("rom", nargs="?")
    ap.add_argument("--hz", type=float, default=MASTER_HZ)
    ap.add_argument("--record", help="save the session as a GIF")
    ap.add_argument("--frames", type=int, help="run this many 60 Hz frames without a terminal")
    ap.add_argument("--dump", action="store_true", help="with --frames: print the final screen")
    a = ap.parse_args()
    mc = Machine(a.mount)
    if a.rom:
        load_program(mc, a.rom)
    if a.frames:
        t0 = time.time()
        (mc.ctl / "clock").write_text(f"{a.frames * MASTER_HZ // 60}\n")
        dt = time.time() - t0
        if a.dump:
            for r in mc.rows():
                print("".join("#" if r >> c & 1 else "." for c in range(64)))
        print(f"{a.frames} frames in {dt:.2f}s ({a.frames / 60 / dt:.2f}x real time)",
              file=sys.stderr)
        return
    play(mc, a.hz, a.record)


if __name__ == "__main__":
    main()
