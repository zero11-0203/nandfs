#!/usr/bin/env python3
"""Run each test program on the reference emulator and on the
Verilog CHIP-8 (Icarus), and require identical traces and final screens.

    lockstep_verilog.py SIM_BINARY WORKDIR [NAME ...]

Runs the programs listed in tests/suite.txt (or those whose names contain one
of the NAMEs). A program X.asm may have a key script X.keys next to it.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import c8asm  # noqa: E402
import chip8ref  # noqa: E402
from loadrom import image_for  # noqa: E402
from tracecmp import compare  # noqa: E402


def load(prog):
    prog = Path(prog)
    if prog.suffix == ".asm":
        return c8asm.assemble(prog.read_text())
    return prog.read_bytes()


def screen_text(m):
    return ["".join("#" if row >> c & 1 else "." for c in range(64)) for row in m.screen]


def suite(names=()):
    """(program path, slots, pokes) for each program in tests/suite.txt."""
    for line in (ROOT / "tests" / "suite.txt").read_text().splitlines():
        f = line.split("#")[0].split()
        if f and (not names or any(n in f[0] for n in names)):
            pokes = [tuple(int(x, 0) for x in p.split("=")) for p in f[2:]]
            yield ROOT / f[0], int(f[1]), pokes


def keys_for(prog):
    keyfile = prog.with_suffix(".keys")
    return chip8ref.parse_keys(keyfile.read_text()) if keyfile.exists() else []


def run_one(sim, work, prog, slots, pokes):
    rom = load(prog)
    keys = keys_for(prog)
    m, ref = chip8ref.run(rom, slots, keys, poke=pokes)
    image = image_for(rom, pokes)
    memh = work / (prog.stem + ".memh")
    memh.write_text("\n".join("%02x" % b for b in image) + "\n")
    kev = work / (prog.stem + ".kev")
    kev.write_text("".join("%x\n%x\n" % e for e in keys))
    out = subprocess.run([sim, f"+rom={memh}", f"+keys={kev}", f"+slots={slots}", "+screen"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    out = [l for l in out if l and not l.startswith("VCD")]
    hw_screen = [l for l in out if set(l) <= set("#.") and len(l) == 64]
    hw = [l for l in out if l.split()[0].isdigit()]
    msg = compare(ref, hw, ("ref", "verilog"))
    if not msg and hw_screen != screen_text(m):
        msg = "final screens differ"
    print(f"{prog.name:24} {len(ref):6} instructions  " + ("ok" if not msg else "FAIL"))
    if msg:
        print(msg)
    return not msg


def main():
    sim, work = sys.argv[1], Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    ok = all([run_one(sim, work, *t) for t in suite(sys.argv[3:])])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
