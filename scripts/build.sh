#!/bin/sh
# build.sh: compile the daemon, synthesize the CHIP-8 to NAND gates, and write
# the folder computer. Steps whose inputs have not changed are skipped.
#
#   NANDFS_BUILD   where generated files go (default ~/nandfs-build; it holds
#                  about a million small files, so use a fast local disk)
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
mkdir -p "$OUT/net" "$SRC/build"

make -s -C "$SRC/fs"

HW="$SRC/hw/chip8/chip8.v $SRC/hw/chip8/memtree.v"
NET=$OUT/net/chip8.json
if [ ! -f "$NET" ] || [ -n "$(find $HW "$SRC/scripts/synth.sh" -newer "$NET")" ]; then
    echo "synthesizing hw/chip8 to NAND gates..."
    "$SRC/scripts/synth.sh" chip8 "$NET" $HW
    rm -rf "$OUT/tree"
fi

if [ ! -d "$OUT/tree/chip8" ] || [ -n "$(find "$SRC/tools/netlist2folders.py" -newer "$OUT/tree")" ]; then
    echo "writing the folder computer (about a million files)..."
    rm -rf "$OUT/tree.tmp"
    python3 "$SRC/tools/netlist2folders.py" "$NET" "$OUT/tree.tmp" chip8
    rm -rf "$OUT/tree"
    mv "$OUT/tree.tmp" "$OUT/tree"
fi

for f in "$SRC"/roms/*.asm; do
    python3 "$SRC/tools/c8asm.py" "$f" "$SRC/build/$(basename "${f%.asm}").ch8"
done
echo "built: $OUT/tree"
