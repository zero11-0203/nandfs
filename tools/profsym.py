#!/usr/bin/env python3
"""Sum an rvref profile (-p) by function: profsym.py PROFILE ELF [N]"""
import bisect
import subprocess
import sys

prof, elf = sys.argv[1], sys.argv[2]
top = int(sys.argv[3]) if len(sys.argv) > 3 else 30
syms = []
for line in subprocess.run(["riscv64-unknown-elf-nm", "-n", elf], capture_output=True,
                           text=True).stdout.splitlines():
    f = line.split()
    if len(f) == 3 and f[1] in "tT":
        syms.append((int(f[0], 16), f[2]))
addrs = [a for a, _ in syms]
count = {}
total = 0
for line in open(prof):
    pc, n = line.split()
    n = int(n)
    i = bisect.bisect_right(addrs, int(pc, 16)) - 1
    name = syms[i][1] if i >= 0 else "?"
    count[name] = count.get(name, 0) + n
    total += n
for name, n in sorted(count.items(), key=lambda kv: -kv[1])[:top]:
    print(f"{n:12d} {100 * n / total:5.1f}%  {name}")
print(f"{total:12d} total")
