#!/bin/sh
# build-rv32.sh: synthesize the RV32IM machine (hw/rv32 around PicoRV32) to NAND gates and
# write it as folders in $NANDFS_BUILD/rvtree; build rvref, the test programs
# and (if its sources were fetched with scripts/fetch-doom.sh) DOOM.
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
mkdir -p "$OUT/net" "$OUT/sim"

make -s -C "$SRC/fs"
cc -O2 -Wall -o "$OUT/rvref" "$SRC/tools/rvref.c"

[ -d "$OUT/picorv32" ] || "$SRC/scripts/fetch-picorv32.sh" >/dev/null
PICO=$OUT/picorv32/picorv32.v
HW="$SRC/hw/rv32/rv32.v $SRC/hw/rv32/hostmem.v $PICO"
NET=$OUT/net/rv32.json
if [ ! -f "$NET" ] || [ -n "$(find $HW "$SRC/scripts/synth.sh" -newer "$NET")" ]; then
    echo "synthesizing hw/rv32 to NAND gates..."
    # -nofsm keeps PicoRV32's state encoding, which the lockstep test reads.
    SYNTH_OPTS=-nofsm "$SRC/scripts/synth.sh" rv32 "$NET" $HW
    rm -rf "$OUT/rvtree"
fi
if [ ! -d "$OUT/rvtree/rv32" ] || [ -n "$(find "$SRC/tools/netlist2folders.py" -newer "$OUT/rvtree")" ]; then
    echo "writing the folder computer..."
    rm -rf "$OUT/rvtree.tmp"
    python3 "$SRC/tools/netlist2folders.py" "$NET" "$OUT/rvtree.tmp" rv32
    rm -rf "$OUT/rvtree"
    mv "$OUT/rvtree.tmp" "$OUT/rvtree"
fi
iverilog -g2012 -DRISCV_FORMAL -o "$OUT/sim/rv32" -s tb "$SRC/hw/rv32/tb.v" \
    "$SRC/hw/rv32/rv32.v" "$SRC/hw/rv32/hostmem_sim.v" "$PICO"

[ -d "$OUT/riscv-tests" ] || "$SRC/scripts/fetch-riscv-tests.sh" >/dev/null
make -s -C "$SRC/sw/isa" 2>&1 | grep -v "RWX permissions" || true
make -s -C "$SRC/sw" >/dev/null
if [ -d "$OUT/doom/doomgeneric" ]; then make -s -C "$SRC/sw/doom" >/dev/null; fi
echo "built: $OUT/rvtree"
