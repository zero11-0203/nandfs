#!/bin/sh
# rambench.sh: gate evaluations per tick for 4 KB of RAM accessed at random
# addresses, built two ways: the plain Verilog array (hw/test/rambench.v),
# which Yosys turns into a flat decoder and multiplexer, and the 16-way tree
# the CHIP-8 uses (hw/test/rambench2.v, hw/chip8/memtree.v).
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
MNT=$OUT/rambench-mnt
make -s -C "$SRC/fs"
mkdir -p "$OUT/net"
trap '"$SRC/scripts/unmount.sh" "$MNT"' EXIT
for top in rambench rambench2; do
    "$SRC/scripts/synth.sh" $top "$OUT/net/$top.json" "$SRC/hw/test/$top.v" "$SRC/hw/chip8/memtree.v"
    rm -rf "$OUT/$top"
    python3 "$SRC/tools/netlist2folders.py" "$OUT/net/$top.json" "$OUT/$top" $top >/dev/null
    "$SRC/scripts/mount.sh" "$OUT/$top" "$MNT"
    echo 2000 > "$MNT/.ctl/clock"
    e0=$(grep evals_total "$MNT/.ctl/stats" | cut -d' ' -f2)
    echo 10000 > "$MNT/.ctl/clock"
    e1=$(grep evals_total "$MNT/.ctl/stats" | cut -d' ' -f2)
    printf "%-10s %7s NAND gates, %6d gate evaluations per access\n" $top \
        "$(grep '^nand ' "$MNT/.ctl/stats" | cut -d' ' -f2)" $(((e1 - e0) / 10000))
    "$SRC/scripts/unmount.sh" "$MNT"
done
