#!/usr/bin/env python3
"""Drive viewer/play.py through a pseudo-terminal: hold "up" for a while,
then quit with Esc, and check that frames were drawn and the game ran.

    viewer_smoke.py MOUNT ROM
"""
import os
import pty
import re
import select
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
mount, rom = sys.argv[1], sys.argv[2]
pid, fd = pty.fork()
if pid == 0:
    os.execvp(sys.executable, [sys.executable, str(ROOT / "viewer" / "play.py"), mount, rom])
out = b""


def drain(timeout):
    global out
    if select.select([fd], [], [], timeout)[0]:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            return False
        out += chunk
        return bool(chunk)
    return True


# Loading the ROM can take a while after the mount has been reloaded, and
# until the first frame the terminal is still in line mode, so wait for it.
deadline = time.time() + 120
while b"\x1b[H" not in out and time.time() < deadline:
    drain(0.1)
t0 = next_key = time.time()
while time.time() - t0 < 6:
    if time.time() - t0 > 2 and time.time() >= next_key:
        os.write(fd, b"1")          # hold key 1 (left paddle up): 20 Hz key repeat
        next_key += 0.05
    while select.select([fd], [], [], 0.01)[0]:
        out += os.read(fd, 65536)
os.write(fd, b"\x1b")
deadline = time.time() + 10
while drain(0.1):
    if time.time() > deadline:
        print("the viewer did not quit on Esc")
        os.kill(pid, signal.SIGINT)
        time.sleep(2)
        sys.exit(1)
os.waitpid(pid, 0)
text = out.decode(errors="ignore")
frames = text.count("\x1b[H")
status = re.findall(r"(\d+\.\d) kHz\s+(\d+) instr/s\s+(\d+) gates/tick", text)
print(f"{frames} frames drawn; last status: {status[-1] if status else None}")
last = text.split("\x1b[H")[-2] if frames > 1 else ""
print("\n".join(l for l in last.splitlines()[:18]))
sys.exit(0 if 100 < frames < 300 and status else 1)
