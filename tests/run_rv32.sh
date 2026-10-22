#!/bin/sh
# run_rv32.sh [quick]: checks for the RV32IM machine, on riscv-tests rv32ui
# and rv32um plus two tests of our own (sw/isa): 50 programs.
#   1. Verilog (Icarus) vs tools/rvref.c, instruction by instruction
#      (slow, skipped by "quick")
#   2. folder machine vs tools/rvref.c, instruction by instruction
# The folder test runs on its own copy of the tree, because a .mem's data
# file lives in the backing tree and run-doom.sh may be using rvtree.
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
MNT=$OUT/rvtest-mnt
TREE=$OUT/rvtest-tree
"$SRC/scripts/build-rv32.sh" >/dev/null
PROGS=$(sed "s|^|$OUT/sw/isa/|; s|\$|.bin|" "$OUT/sw/isa/list.txt")
cleanup() { "$SRC/scripts/unmount.sh" "$MNT"; }
trap cleanup EXIT

if [ "${1:-}" != quick ]; then
    echo "== 1. Verilog vs reference"
    python3 "$SRC/tests/rv_lockstep_verilog.py" "$OUT/sim/rv32" "$OUT/rvref" $PROGS
fi

echo "== 2. folders vs reference"
rm -rf "$TREE"
cp -a "$OUT/rvtree" "$TREE"
"$SRC/scripts/mount.sh" "$TREE" "$MNT"
python3 -u "$SRC/tests/rv_lockstep_folders.py" "$MNT" "$OUT/rvref" $PROGS
echo "all checks passed"
