#!/usr/bin/env python3
"""Speed of the mounted RV32IM folder computer running DOOM.

    rv_bench.py MOUNT RAM.bin ROM.rom [SKIP_TICKS] [CHUNKS] [TICKS_PER_CHUNK]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from rvload import load  # noqa: E402

m = Path(sys.argv[1])
skip, chunks, n = (int(x) for x in (sys.argv[4:] + ["0", "3", "2000000"][len(sys.argv) - 4:])[:3])
load(m, sys.argv[2], sys.argv[3])
st = lambda: dict(l.split(" ", 1) for l in (m / ".ctl/stats").read_text().splitlines())  # noqa: E731
num = lambda p: int((m / p).read_text())  # noqa: E731
if skip:
    (m / ".ctl/clock").write_text(f"{skip}\n")
for _ in range(chunks):
    e0, i0, t0 = int(st()["evals_total"]), num("rv32/instret"), time.time()
    (m / ".ctl/clock").write_text(f"{n}\n")
    dt = time.time() - t0
    e1, i1 = int(st()["evals_total"]), num("rv32/instret")
    print(f"{i1:>10} instructions: {(i1 - i0) / dt:6.0f} instr/s, {n / dt:6.0f} ticks/s, "
          f"{(e1 - e0) / (i1 - i0):5.0f} evals/instr, {(e1 - e0) / dt / 1e6:5.1f} M evals/s", flush=True)
