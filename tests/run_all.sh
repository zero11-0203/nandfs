#!/bin/sh
# run_all.sh [quick]: every check, bottom layer first.
#   1. gate demos (NAND, XOR, adders, NAND-built flip-flop, .mem)
#   2. Yosys pipeline on a small Verilog design
#   3. integrity: the simulator knows nothing about CHIP-8
#   4. Verilog CHIP-8 vs reference emulator (Icarus; slow, skipped by "quick")
#   5. folder CHIP-8 vs reference emulator
#   6. the terminal viewer, and reads racing a running machine
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
MNT=$OUT/test-mnt
cd "$SRC"
"$SRC/scripts/build.sh" >/dev/null
[ -d build/roms ] || scripts/fetch-roms.sh >/dev/null
[ -d build/games ] || scripts/fetch-games.sh >/dev/null
cleanup() { "$SRC/scripts/unmount.sh" "$MNT"; }
trap cleanup EXIT

echo "== 1. gate demos"
python3 tools/demos.py "$OUT/demos" >/dev/null
scripts/mount.sh "$OUT/demos" "$MNT"
python3 tests/test_gates.py "$MNT"
cleanup

echo "== 2. Yosys pipeline"
scripts/synth.sh top "$OUT/net/counter.json" hw/test/counter.v
rm -rf "$OUT/vtest"
python3 tools/netlist2folders.py "$OUT/net/counter.json" "$OUT/vtest" top >/dev/null
scripts/mount.sh "$OUT/vtest" "$MNT"
python3 tests/test_pipeline.py "$MNT"
cleanup

echo "== 3. integrity"
sh tests/integrity.sh

if [ "${1:-}" != quick ]; then
    echo "== 4. Verilog vs reference"
    mkdir -p "$OUT/sim"
    iverilog -g2012 -o "$OUT/sim/chip8" -s tb hw/chip8/tb.v hw/chip8/chip8.v hw/chip8/memtree.v
    python3 tests/lockstep_verilog.py "$OUT/sim/chip8" "$OUT/sim"
fi

echo "== 5. folders vs reference"
scripts/mount.sh "$OUT/tree" "$MNT"
python3 -u tests/lockstep_folders.py "$MNT"

echo "== 6. viewer"
python3 tests/viewer_smoke.py "$MNT" build/pong.ch8
python3 tests/read_race.py "$MNT" build/pong.ch8 5
echo "all checks passed"
