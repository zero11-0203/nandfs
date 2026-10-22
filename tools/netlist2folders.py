#!/usr/bin/env python3
"""Turn a Yosys JSON netlist (cells $_NAND_, $_NOT_, $_DFF_P_, hostmem and
module instances, as written by scripts/synth.sh) into a folder computer.

    netlist2folders.py NETLIST.json OUTDIR NAME [--top TOP] [--clock clk]

OUTDIR/NAME/ is the top module. Its inputs (except the clock) become pins in
pins/PORT/BIT.pin, and every top-level port P gets a bus folder P.bus and a
symlink P -> P.bus/value, so `echo 5 > NAME/a` and `cat NAME/sum` work.

Each module instance is a folder holding its gates, its flip-flops, its
sub-instances, a bus for each register (so `cat cpu/pc` prints a number), and
two folders of port symlinks:
    in/PORT/BIT   -> the signal driving this input in the parent
    out/PORT/BIT  -> the signal inside that drives this output
A $_NOT_ becomes a NAND with both inputs on the same wire. A hostmem
(hw/rv32/hostmem.v) becomes a NAME.mem folder: links a0.., w0..w31, we0..we3
and a data file of 4 << (address bits) bytes, all zeros (a sparse file).
Every flip-flop must be clocked by the top-level clock; there is one clock
domain.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

CHUNK = 1000   # most primitives per folder; bigger modules are split into g000/, g001/, ...


def clean(name):
    """A folder name for a Yosys name. An instance made by a generate loop,
    like `r[10].row`, is named by its block and index: `r10`. Blocks whose
    names end in _hex count in hex: `h_hex[10].sub.m` becomes `ha`."""
    name = name.lstrip("\\")
    m = re.fullmatch(r"(\w+)\[(\d+)\]\.[\w.]+", name)
    if m:
        i = int(m.group(2))
        b = m.group(1)
        return b[:-4] + f"{i:x}" if b.endswith("_hex") else b + str(i)
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "x"


class Writer:
    def __init__(self, design, out, clock):
        self.mods = design["modules"]
        self.out = Path(out)
        self.clock = clock
        self.counts = {"nand": 0, "dff": 0, "pin": 0, "link": 0, "dir": 0}
        self.clock_ports = {}

    # -- clocks: which input bits of a module reach a flip-flop clock --
    def clocks_of(self, mname):
        if mname in self.clock_ports:
            return self.clock_ports[mname]
        m = self.mods[mname]
        port_of = {}
        for pname, p in m["ports"].items():
            if p["direction"] == "input":
                for i, b in enumerate(p["bits"]):
                    port_of[b] = (pname, i)
        need = set()
        for cname, c in m["cells"].items():
            t = c["type"]
            if t == "$_DFF_P_":
                bits = [c["connections"]["C"][0]]
            elif t == "hostmem":
                bits = [c["connections"]["clk"][0]]
            elif t in self.mods:
                sub = self.clocks_of(t)
                bits = [c["connections"][p][i] for p, i in sub]
            else:
                continue
            for b in bits:
                if b not in port_of:
                    sys.exit(f"{mname}/{cname}: flip-flop clock is not a module input")
                need.add(port_of[b])
        self.clock_ports[mname] = need
        return need

    def mkdir(self, path):
        path.mkdir(parents=True, exist_ok=True)
        self.counts["dir"] += 1

    def link(self, at, signal):
        at.parent.mkdir(parents=True, exist_ok=True)
        at.symlink_to(os.path.relpath(signal, at.parent))
        self.counts["link"] += 1

    def instance(self, mname, folder, inputs, top=False):
        """Write one module instance into `folder`. `inputs` maps (port, bit)
        to the absolute signal path driving it; returns the same for outputs."""
        m = self.mods[mname]
        self.mkdir(folder)
        sig = {"0": self.gnd, "1": self.vcc, "x": self.gnd, "z": self.gnd}

        for pname, p in m["ports"].items():
            if p["direction"] != "input":
                continue
            for i, b in enumerate(p["bits"]):
                if (pname, i) in self.clocks_of(mname):
                    continue
                at = folder / "in" / clean(pname) / str(i)
                self.link(at, inputs[(pname, i)])
                if isinstance(b, int):
                    sig.setdefault(b, at)

        names = {}
        for nname, n in m["netnames"].items():
            if n["hide_name"]:
                continue
            for i, b in enumerate(n["bits"]):
                if isinstance(b, int) and b not in names:
                    names[b] = clean(nname) + (f"_{i}" if len(n["bits"]) > 1 else "")
        inits = {}
        for nname, n in m["netnames"].items():
            init = n["attributes"].get("init")
            if init:
                for i, b in enumerate(n["bits"]):
                    if isinstance(b, int) and i < len(init):
                        inits[b] = init[-1 - i]

        prims = [(c, n) for n, c in m["cells"].items() if c["type"] in ("$_NAND_", "$_NOT_", "$_DFF_P_")]
        subs = [(c, n) for n, c in m["cells"].items()
                if c["type"] in self.mods and c["type"] != "hostmem"]
        mems = [(c, n) for n, c in m["cells"].items() if c["type"] == "hostmem"]
        other = {c["type"] for c in m["cells"].values()} - {"$_NAND_", "$_NOT_", "$_DFF_P_"} - set(self.mods)
        if other:
            sys.exit(f"{mname}: unsupported cells {sorted(other)}")

        used, plan = set(), []
        for k, (c, cname) in enumerate(prims):
            dff = c["type"] == "$_DFF_P_"
            y = c["connections"]["Q" if dff else "Y"][0]
            base = names.get(y) or ("r" if dff else "g") + str(k)
            nm, j = base, 1
            while nm in used:
                nm, j = f"{base}_{j}", j + 1
            used.add(nm)
            where = folder if len(prims) <= CHUNK else folder / f"g{k // CHUNK:03d}"
            path = where / (nm + (".dff" if dff else ".nand"))
            sig[y] = path / ("q" if dff else "out")
            plan.append((c, path, dff, y))

        sub_out = []
        for c, cname in subs:
            sub_out.append((c, folder / clean(cname)))
            sm = self.mods[c["type"]]
            for pname, p in sm["ports"].items():
                if p["direction"] == "output":
                    for i, b in enumerate(c["connections"].get(pname, [])):
                        if isinstance(b, int):
                            sig.setdefault(b, folder / clean(cname) / "out" / clean(pname) / str(i))

        mem_plan = []
        for c, cname in mems:
            path = folder / (clean(cname) + ".mem")
            for i, b in enumerate(c["connections"]["r"]):
                if isinstance(b, int):
                    sig.setdefault(b, path / f"r{i}")
            mem_plan.append((c, path))

        def s(b):
            if b not in sig:
                sys.exit(f"{mname}: bit {b} has no driver")
            return sig[b]

        for c, path, dff, y in plan:
            self.mkdir(path)
            if dff:
                self.link(path / "d", s(c["connections"]["D"][0]))
                (path / "init").write_text(inits.get(y, "0") + "\n")
                self.counts["dff"] += 1
            else:
                a = s(c["connections"]["A"][0])
                b = a if c["type"] == "$_NOT_" else s(c["connections"]["B"][0])
                self.link(path / "a", a)
                self.link(path / "b", b)
                self.counts["nand"] += 1

        for c, path in mem_plan:
            self.mkdir(path)
            cn = c["connections"]
            for port, prefix in (("a", "a"), ("w", "w"), ("we", "we")):
                for i, b in enumerate(cn[port]):
                    self.link(path / f"{prefix}{i}", s(b))
            with open(path / "data", "wb") as f:
                f.truncate(4 << len(cn["a"]))
            self.counts["mem"] = self.counts.get("mem", 0) + 1

        for c, sub_folder in sub_out:
            sm = self.mods[c["type"]]
            sub_in, sub_clk = {}, self.clocks_of(c["type"])
            for pname, p in sm["ports"].items():
                if p["direction"] == "input":
                    for i, b in enumerate(c["connections"][pname]):
                        if (pname, i) not in sub_clk:
                            sub_in[(pname, i)] = s(b)
            self.instance(c["type"], sub_folder, sub_in)

        # A register (a named net of 2-64 flip-flops, some bits perhaps
        # constant) is readable as a number: NAME.bus holds its bits and
        # NAME -> NAME.bus/value.
        dff_q = {y: path / "q" for c, path, dff, y in plan if dff}
        const = {"0": self.gnd, "1": self.vcc}
        for nname, n in m["netnames"].items():
            bits, nm = n["bits"], clean(nname)
            if n["hide_name"] or not 2 <= len(bits) <= 64 or not any(b in dff_q for b in bits) \
                    or not all(b in dff_q or b in const for b in bits):
                continue
            if top and nname in m["ports"]:   # top() makes a bus for each top port
                continue
            if (folder / nm).exists() or (folder / (nm + ".bus")).exists():
                continue
            self.mkdir(folder / (nm + ".bus"))
            for i, b in enumerate(bits):
                self.link(folder / (nm + ".bus") / str(i), dff_q[b] if b in dff_q else const[b])
            self.link(folder / nm, folder / (nm + ".bus") / "value")

        outs = {}
        for pname, p in m["ports"].items():
            if p["direction"] == "output":
                for i, b in enumerate(p["bits"]):
                    at = folder / "out" / clean(pname) / str(i)
                    self.link(at, s(b))
                    outs[(pname, i)] = at
        return outs

    def top(self, tname, name):
        self.vcc, self.gnd = self.out / "vcc" / "out", self.out / "gnd" / "out"
        folder = self.out / name
        m = self.mods[tname]
        clocks = self.clocks_of(tname)
        if any(p != self.clock for p, _ in clocks):
            sys.exit(f"flip-flops are clocked by {sorted(clocks)}, not only {self.clock}")
        inputs = {}
        for pname, p in m["ports"].items():
            if p["direction"] != "input" or pname == self.clock:
                continue
            for i in range(len(p["bits"])):
                pin = folder / "pins" / clean(pname) / f"{i}.pin"
                self.mkdir(pin)
                (pin / "value").write_text("0\n")
                self.counts["pin"] += 1
                inputs[(pname, i)] = pin / "out"
        outs = self.instance(tname, folder, inputs, top=True)
        for pname, p in m["ports"].items():
            if pname == self.clock:
                continue
            bus = folder / (clean(pname) + ".bus")
            self.mkdir(bus)
            for i in range(len(p["bits"])):
                src = inputs[(pname, i)] if p["direction"] == "input" else outs[(pname, i)]
                self.link(bus / str(i), src)
            self.link(folder / clean(pname), bus / "value")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("outdir")
    ap.add_argument("name")
    ap.add_argument("--top")
    ap.add_argument("--clock", default="clk")
    a = ap.parse_args()
    design = json.load(open(a.netlist))
    top = a.top or next(n for n, m in design["modules"].items() if m["attributes"].get("top"))
    w = Writer(design, a.outdir, a.clock)
    if (Path(a.outdir) / a.name).exists():
        sys.exit(f"{Path(a.outdir) / a.name} already exists")
    w.top(top, a.name)
    print(" ".join(f"{k}={v}" for k, v in w.counts.items()))


if __name__ == "__main__":
    main()
