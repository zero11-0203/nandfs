"""Write circuits as folders: the vocabulary nandfs understands.

A signal is the path (relative to the tree root) of the file that carries it:
"vcc/out", "adder/fa0/x1.nand/out", "cpu/pc3.dff/q". Every wire is a relative
symlink, so any subtree can be copied with cp -R.
"""
import os
from pathlib import Path

VCC, GND, CLK = "vcc/out", "gnd/out", "clk/out"


class Tree:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.nands = self.dffs = 0

    def _dir(self, path):
        d = self.root / path
        d.mkdir(parents=True, exist_ok=False)
        return d

    def link(self, at, signal):
        """Make the symlink `at` (a path in the tree) point at `signal`."""
        at = self.root / at
        at.parent.mkdir(parents=True, exist_ok=True)
        target = os.path.relpath(self.root / signal, at.parent)
        if at.is_symlink():
            at.unlink()
        at.symlink_to(target)

    def nand(self, path, a, b, init=None):
        d = self._dir(path + ".nand")
        self.link(f"{path}.nand/a", a)
        self.link(f"{path}.nand/b", b)
        if init is not None:
            (d / "init").write_text(f"{init}\n")
        self.nands += 1
        return f"{path}.nand/out"

    def dff(self, path, d=None, init=0):
        d_ = self._dir(path + ".dff")
        (d_ / "init").write_text(f"{init}\n")
        if d is not None:
            self.link(f"{path}.dff/d", d)
        self.dffs += 1
        return f"{path}.dff/q"

    def pin(self, path, value=0):
        d = self._dir(path + ".pin")
        (d / "value").write_text(f"{value}\n")
        return f"{path}.pin/out"

    def bus(self, path, bits):
        """A bus folder: bit i is the symlink path.bus/i. Returns path.bus/value."""
        self._dir(path + ".bus")
        for i, s in enumerate(bits):
            self.link(f"{path}.bus/{i}", s)
        return f"{path}.bus/value"

    def mem(self, path, addr, wdata=(), we=(), size=0, data=None):
        """A .mem: words of 32 bits in the file path.mem/data (`size` bytes of
        zeros, or `data`). Returns the 32 read-bit signals."""
        d = self._dir(path + ".mem")
        (d / "data").write_bytes(data if data is not None else bytes(size))
        for i, s in enumerate(addr):
            self.link(f"{path}.mem/a{i}", s)
        for i, s in enumerate(wdata):
            self.link(f"{path}.mem/w{i}", s)
        for i, s in enumerate(we):
            self.link(f"{path}.mem/we{i}", s)
        return [f"{path}.mem/r{i}" for i in range(32)]

    def port(self, path, signal):
        """A module port: a plain symlink naming a signal inside the module."""
        self.link(path, signal)
        return path

    # Small cells built from NAND, used by the hand-written demos.

    def not_(self, path, a):
        return self.nand(path, a, a)

    def and_(self, path, a, b):
        return self.not_(path + "_n", self.nand(path, a, b))

    def xor(self, path, a, b):
        n1 = self.nand(f"{path}/n1", a, b)
        n2 = self.nand(f"{path}/n2", a, n1)
        n3 = self.nand(f"{path}/n3", b, n1)
        return self.nand(f"{path}/n4", n2, n3)

    def full_adder(self, path, a, b, cin):
        """The classic nine-NAND full adder. Returns (sum, carry_out)."""
        n1 = self.nand(f"{path}/n1", a, b)
        n2 = self.nand(f"{path}/n2", a, n1)
        n3 = self.nand(f"{path}/n3", b, n1)
        s1 = self.nand(f"{path}/n4", n2, n3)
        n5 = self.nand(f"{path}/n5", s1, cin)
        n6 = self.nand(f"{path}/n6", s1, n5)
        n7 = self.nand(f"{path}/n7", cin, n5)
        s = self.nand(f"{path}/sum", n6, n7)
        c = self.nand(f"{path}/cout", n1, n5)
        return s, c

    def d_latch(self, path, d, en):
        """Gated D latch from four NANDs; holds while en is 0. Returns q."""
        s = self.nand(f"{path}/s", d, en, init=1)
        r = self.nand(f"{path}/r", s, en, init=1)
        q = f"{path}/q.nand/out"
        qb = self.nand(f"{path}/qb", r, q, init=1)
        self.nand(f"{path}/q", s, qb, init=0)
        return q

    def nand_dff(self, path, d):
        """Rising-edge D flip-flop from NAND gates only: a master latch open
        while clk is low feeding a slave latch open while clk is high."""
        nclk = self.not_(f"{path}/nclk", CLK)
        m = self.d_latch(f"{path}/master", d, nclk)
        q = self.d_latch(f"{path}/slave", m, CLK)
        return self.port(f"{path}/q", q)
