#!/usr/bin/env python3
"""Reference CHIP-8 machine: the specification the gate-level machine must match.

    chip8ref.py ROM [--slots N] [--keys SCRIPT] [--trace]

It models the hardware's timing exactly, at the level of instruction slots:

  * A slot is 32 master clock ticks; one instruction starts in each slot and
    always finishes within it. FRAME slots (default 12) make one 60 Hz frame.
  * At the start of every slot the 16-bit random-number LFSR steps once.
  * At the start of every frame (slot 0) the delay and sound timers count down.
  * DXYN (COSMAC VIP display-wait quirk) waits for the next frame start, then
    draws during that frame's slot 0.
  * FX0A runs once per slot until a key has been pressed and released.

Quirks are those of the original COSMAC VIP interpreter: 8XY1/2/3 reset VF;
8XY6/8XYE shift VY into VX; FX55/FX65 advance I by X+1; sprites wrap their
start position but clip at the screen edge; BNNN jumps to V0 + NNN. I is 12
bits wide: addresses wrap at 4 KB, so higher bits could never be observed.

A trace line is written each time an instruction finishes:
    slot pc v0..vf i sp dt st
"""
import argparse
import sys

FONT = [
    0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70,
    0xF0, 0x10, 0xF0, 0x80, 0xF0, 0xF0, 0x10, 0xF0, 0x10, 0xF0,
    0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0,
    0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40,
    0xF0, 0x90, 0xF0, 0x90, 0xF0, 0xF0, 0x90, 0xF0, 0x10, 0xF0,
    0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
    0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0,
    0xF0, 0x80, 0xF0, 0x80, 0xF0, 0xF0, 0x80, 0xF0, 0x80, 0x80,
]
FRAME = 12
LFSR_SEED = 0xACE1


def lfsr_step(x):
    """16-bit Fibonacci LFSR, taps 16 14 13 11; shifts left."""
    bit = ((x >> 15) ^ (x >> 13) ^ (x >> 12) ^ (x >> 10)) & 1
    return ((x << 1) | bit) & 0xFFFF


class Chip8:
    def __init__(self, rom, frame=FRAME, poke=()):
        self.mem = bytearray(4096)
        self.mem[0x200:0x200 + len(rom)] = rom
        for a, b in poke:
            self.mem[a] = b
        self.frame = frame
        self.v = [0] * 16
        self.i = self.sp = self.dt = self.st = 0
        self.pc = 0x200
        self.stack = [0] * 16
        self.screen = [0] * 32          # rows; bit c is column c (0 = left)
        self.lfsr = LFSR_SEED
        self.slot = 0                   # slots completed since reset
        self.keys = 0                   # bit k set while key k is held
        self.waiting_draw = None
        self.key_pressed = False        # FX0A: a key went down, waiting for release
        self.key_seen = 0

    def read(self, a):
        a &= 0xFFF
        return FONT[a] if a < 0x50 else self.mem[a]

    def write(self, a, b):
        self.mem[a & 0xFFF] = b & 0xFF

    def state(self):
        return (self.pc, *self.v, self.i, self.sp, self.dt, self.st)

    def draw(self, x, y, n):
        x0, y0, hit = self.v[x] & 63, self.v[y] & 31, 0
        for r in range(n):
            if y0 + r > 31:
                break
            row = self.mem_sprite(self.i + r)
            mask = 0
            for k in range(8):
                if (row >> (7 - k)) & 1 and x0 + k < 64:
                    mask |= 1 << (x0 + k)
            if self.screen[y0 + r] & mask:
                hit = 1
            self.screen[y0 + r] ^= mask
        self.v[15] = hit

    def mem_sprite(self, a):
        return self.read(a)

    def step_slot(self):
        """Run one slot. Returns True if an instruction finished in it."""
        self.lfsr = lfsr_step(self.lfsr)
        frame_start = self.slot % self.frame == 0
        if frame_start:
            self.dt = max(self.dt - 1, 0)
            self.st = max(self.st - 1, 0)
        self.slot += 1
        if self.waiting_draw:
            if not frame_start:
                return False
            self.draw(*self.waiting_draw)
            self.waiting_draw = None
            return True
        return self.execute()

    def execute(self):
        hi, lo = self.read(self.pc), self.read(self.pc + 1)
        op = hi << 8 | lo
        self.pc = (self.pc + 2) & 0xFFF
        x, y, n, nn, nnn = hi & 15, lo >> 4, lo & 15, lo, op & 0xFFF
        v = self.v
        top = hi >> 4
        if op == 0x00E0:
            self.screen = [0] * 32
        elif op == 0x00EE:
            self.sp = (self.sp - 1) & 15
            self.pc = self.stack[self.sp]
        elif top == 0x1:
            self.pc = nnn
        elif top == 0x2:
            self.stack[self.sp] = self.pc
            self.sp = (self.sp + 1) & 15
            self.pc = nnn
        elif top == 0x3:
            if v[x] == nn:
                self.pc = (self.pc + 2) & 0xFFF
        elif top == 0x4:
            if v[x] != nn:
                self.pc = (self.pc + 2) & 0xFFF
        elif top == 0x5 and n == 0:
            if v[x] == v[y]:
                self.pc = (self.pc + 2) & 0xFFF
        elif top == 0x6:
            v[x] = nn
        elif top == 0x7:
            v[x] = (v[x] + nn) & 0xFF
        elif top == 0x8:
            a, b = v[x], v[y]
            res, flag = None, None
            if n == 0x0:
                res = b
            elif n == 0x1:
                res, flag = a | b, 0
            elif n == 0x2:
                res, flag = a & b, 0
            elif n == 0x3:
                res, flag = a ^ b, 0
            elif n == 0x4:
                res, flag = (a + b) & 0xFF, int(a + b > 0xFF)
            elif n == 0x5:
                res, flag = (a - b) & 0xFF, int(a >= b)
            elif n == 0x6:
                res, flag = b >> 1, b & 1
            elif n == 0x7:
                res, flag = (b - a) & 0xFF, int(b >= a)
            elif n == 0xE:
                res, flag = (b << 1) & 0xFF, b >> 7
            if res is not None:
                v[x] = res
            if flag is not None:
                v[15] = flag
        elif top == 0x9 and n == 0:
            if v[x] != v[y]:
                self.pc = (self.pc + 2) & 0xFFF
        elif top == 0xA:
            self.i = nnn
        elif top == 0xB:
            self.pc = (nnn + v[0]) & 0xFFF
        elif top == 0xC:
            v[x] = self.lfsr & 0xFF & nn
        elif top == 0xD:
            self.waiting_draw = (x, y, n)
            return False
        elif top == 0xE and lo == 0x9E:
            if self.keys >> (v[x] & 15) & 1:
                self.pc = (self.pc + 2) & 0xFFF
        elif top == 0xE and lo == 0xA1:
            if not self.keys >> (v[x] & 15) & 1:
                self.pc = (self.pc + 2) & 0xFFF
        elif top == 0xF:
            if lo == 0x07:
                v[x] = self.dt
            elif lo == 0x0A:
                self.wait_key(x)
            elif lo == 0x15:
                self.dt = v[x]
            elif lo == 0x18:
                self.st = v[x]
            elif lo == 0x1E:
                self.i = (self.i + v[x]) & 0xFFF
            elif lo == 0x29:
                self.i = (v[x] & 15) * 5
            elif lo == 0x33:
                self.write(self.i, v[x] // 100)
                self.write(self.i + 1, v[x] // 10 % 10)
                self.write(self.i + 2, v[x] % 10)
            elif lo == 0x55:
                for k in range(x + 1):
                    self.write(self.i + k, v[k])
                self.i = (self.i + x + 1) & 0xFFF
            elif lo == 0x65:
                for k in range(x + 1):
                    v[k] = self.read(self.i + k)
                self.i = (self.i + x + 1) & 0xFFF
        return True

    def wait_key(self, x):
        """FX0A: note the lowest key held; finish when that key is released."""
        if not self.key_pressed:
            if self.keys:
                self.key_seen = (self.keys & -self.keys).bit_length() - 1
                self.key_pressed = True
        elif not self.keys >> self.key_seen & 1:
            self.v[x] = self.key_seen
            self.key_pressed = False
            return
        self.pc = (self.pc - 2) & 0xFFF


def parse_keys(text):
    """Key script: lines "SLOT KEYMASK" (hex mask), applied from that slot on."""
    events = []
    for line in text.splitlines():
        line = line.split("#")[0].split()
        if line:
            events.append((int(line[0]), int(line[1], 16)))
    return sorted(events)


def run(rom, slots, keys=(), frame=FRAME, out=None, poke=()):
    m = Chip8(rom, frame, poke)
    ev = list(keys)
    trace = []
    for s in range(slots):
        while ev and ev[0][0] <= s:
            m.keys = ev.pop(0)[1]
        if m.step_slot():
            line = "%d " % s + " ".join("%x" % x for x in m.state())
            trace.append(line)
            if out:
                out.write(line + "\n")
    return m, trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--slots", type=int, default=1000)
    ap.add_argument("--keys", help="key script: lines 'SLOT HEXMASK'")
    ap.add_argument("--frame", type=int, default=FRAME)
    ap.add_argument("--poke", action="append", default=[],
                    help="ADDR=BYTE written to memory before start, e.g. 0x1ff=1")
    ap.add_argument("--screen", action="store_true", help="print the screen at the end")
    a = ap.parse_args()
    keys = parse_keys(open(a.keys).read()) if a.keys else []
    poke = [tuple(int(x, 0) for x in p.split("=")) for p in a.poke]
    m, _ = run(open(a.rom, "rb").read(), a.slots, keys, a.frame, sys.stdout, poke)
    if a.screen:
        for row in m.screen:
            print("".join("#" if row >> c & 1 else "." for c in range(64)))


if __name__ == "__main__":
    main()
