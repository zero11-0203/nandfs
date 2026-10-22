#!/usr/bin/env python3
"""Play DOOM on the mounted RV32IM folder computer, in a web browser.

    rvplay.py MOUNT OUTDIR --ram doomplay.bin --rom doom1.rom [--port 8035]
    rvplay.py MOUNT OUTDIR --resume

Open http://localhost:8035 (from the Mac, OrbStack forwards the VM's ports).
Like rvdoom.py the runner only reads and writes files: it clocks the machine
in small chunks (.ctl/clock), writes the key pins (rv32/keys) between chunks,
and when the frame counter in RAM moves it reads the frame and its palette
from rv32/ram.mem/data and hands them to the page. Every frame is also saved
as OUTDIR/frames/frameNNNNN.ppm.

A frame takes the folders two or three minutes, so a key you tap is held
until two frames later (the game must read the pins at a tic boundary to see
it). The buttons on the page latch: click once to hold a key, again to let go.

Every --checkpoint frames, and when stopped with Ctrl-C, the machine is saved
to OUTDIR/checkpoint; --resume carries on from there (skipping the boot).
"""
import argparse
import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from rvdoom import CONSOLE, FRAME, Machine, checkpoint, load, restore

# Bit i of the key pins is DOOM key keymap[i] in sw/doom/doomgeneric_nandfs.c.
KEYS = ["up", "down", "left", "right", "fire", "use", "run", "enter", "esc", "y",
        "strafe left", "strafe right", "map"]


class Game:
    def __init__(self, mc, out, state, chunk):
        self.mc, self.out, self.state, self.chunk = mc, out, state, chunk
        self.lock = threading.Lock()
        self.held = 0           # keys the page says are down
        self.latched = {}       # bit -> frame number until which it stays down
        self.frame_bytes = None
        self.frame_time = time.time()
        self.rate = 0.0
        self.stop = False

    def pins(self):
        with self.lock:
            f = self.state["frame"]
            self.latched = {b: until for b, until in self.latched.items() if f < until}
            return self.held | sum(1 << b for b in self.latched)

    def key(self, bit, down):
        with self.lock:
            if down:
                self.held |= 1 << bit
                self.latched[bit] = self.state["frame"] + 2
            else:
                self.held &= ~(1 << bit)

    def per_frame(self, last=None):
        """Average seconds per frame over the last `last` frames (all if None),
        counting from frame 1 so the boot is left out."""
        log = self.state.get("frame_log", [])
        if last:
            log = log[-(last + 1):]
        if len(log) < 2 or log[-1][0] == log[0][0]:
            return None
        return (log[-1][1] - log[0][1]) / (log[-1][0] - log[0][0])

    def grab(self):
        f = self.state["frame"]
        fb = self.mc.read(0xE00000, 320 * 200)
        pal = self.mc.read(0xE10000, 1024)
        self.frame_bytes = f.to_bytes(4, "little") + pal + fb
        (self.out / "frames" / f"frame{f:05d}.ppm").write_bytes(self.mc.frame_ppm())

    def run(self, every):
        mc, st = self.mc, self.state
        console = open(self.out / "console.txt", "a")
        pins = None
        t0, sec0, ticks0 = time.time(), st["seconds"], st["ticks"]
        if st["frame"]:
            self.grab()
        while not self.stop:
            p = self.pins()
            if p != pins:
                (mc.m / "rv32/keys").write_text(f"{p}\n")
                pins = p
            mc.clock(self.chunk)
            st["ticks"] += self.chunk
            st["seconds"] = sec0 + time.time() - t0
            self.rate = (st["ticks"] - ticks0) / max(time.time() - t0, 1e-9)
            n = mc.u32(CONSOLE)
            if n > st["console"]:
                console.write(mc.read(CONSOLE + 4 + st["console"], n - st["console"])
                              .decode(errors="replace"))
                console.flush()
                st["console"] = n
            f = mc.u32(FRAME)
            if f != st["frame"]:
                st["frame"] = f
                # [frame, seconds of running] for each frame, for the average
                st.setdefault("frame_log", []).append([f, st["seconds"]])
                self.grab()
                self.frame_time = time.time()
                print(f"frame {f} at {st['ticks']} ticks, {st['seconds'] / 3600:.2f} h", flush=True)
                if f % every == 0:
                    checkpoint(mc, self.out, st)
            if mc.num("rv32/halted"):
                print("the machine halted", flush=True)
                break
        checkpoint(mc, self.out, st)
        print(f"saved at frame {st['frame']}", flush=True)


PAGE = (Path(__file__).resolve().parent / "rvplay.html").read_bytes


def handler(game):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body=b"", ctype="application/octet-stream"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/":
                self.send(200, PAGE(), "text/html; charset=utf-8")
            elif path == "/frame":
                have = int(query.partition("=")[2] or -1)
                fb = game.frame_bytes
                if fb is None or int.from_bytes(fb[:4], "little") == have:
                    self.send(204)
                else:
                    self.send(200, fb)
            elif path == "/status":
                st = game.state
                body = {"frame": st["frame"], "ticks": st["ticks"], "rate": game.rate,
                        "since": time.time() - game.frame_time, "pins": game.pins(),
                        "avg": game.per_frame(), "avg10": game.per_frame(10),
                        "instret": game.mc.num("rv32/instret"), "keys": KEYS}
                self.send(200, json.dumps(body).encode(), "application/json")
            else:
                self.send(404)

        def do_POST(self):
            # /key?bit=N&down=0|1
            path, _, query = self.path.partition("?")
            q = dict(kv.split("=") for kv in query.split("&") if "=" in kv)
            if path == "/key" and 0 <= int(q.get("bit", -1)) < len(KEYS):
                game.key(int(q["bit"]), q.get("down") == "1")
                self.send(204)
            else:
                self.send(404)
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mount")
    ap.add_argument("out")
    ap.add_argument("--ram")
    ap.add_argument("--rom")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--port", type=int, default=8035)
    ap.add_argument("--chunk", type=int, default=5000, help="ticks between key pin updates")
    ap.add_argument("--checkpoint", type=int, default=10, help="frames between checkpoints")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    mc = Machine(a.mount)
    if a.resume:
        state = json.loads((out / "checkpoint/state.json").read_text())
        state = restore(mc, out, state["rom"])
        print(f"resumed at frame {state['frame']}, {state['ticks']} ticks", flush=True)
        if "frame_log" not in state:
            # saved by an older version: take the frame times from the files
            files = sorted((out / "frames").glob("frame*.ppm"))
            t = [(int(f.stem[5:]), f.stat().st_mtime) for f in files]
            t = [(n, m) for n, m in t if n <= state["frame"]]
            if t:
                shift = state["seconds"] - t[-1][1]
                state["frame_log"] = [[n, m + shift] for n, m in t]
    else:
        load(a.mount, a.ram, a.rom)
        state = {"ticks": 0, "frame": 0, "console": 0, "seconds": 0.0,
                 "rom": str(Path(a.rom).resolve())}
    game = Game(mc, out, state, a.chunk)
    server = ThreadingHTTPServer(("0.0.0.0", a.port), handler(game))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"open http://localhost:{a.port}  (Ctrl-C saves and stops)", flush=True)

    def stop(*_):
        game.stop = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    game.run(a.checkpoint)
    server.shutdown()


if __name__ == "__main__":
    main()
