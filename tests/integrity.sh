#!/bin/sh
# Rule 3: the simulator knows nothing about the machines it runs (CHIP-8,
# RV32IM). The daemon's source must not mention any part of a machine, and the
# same binary runs every circuit (run_all.sh runs it on the gate demos, the
# Verilog test design and CHIP-8; run_rv32.sh on the RISC-V machine).
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
C=$SRC/fs/nandfs.c
if grep -niwE 'chip-?8|cpu|ram|memory|display|screen|pixels?|opcodes?|registers?|keypad|keys|sprites?|timers?|font|stack|0x200|instructions?|risc-?v|rv32\w*|doom|wad|frame ?buffer|palette|rom|ecall|pc' "$C"; then
    echo "FAIL: the simulator mentions the machine it runs"
    exit 1
fi
echo "ok: fs/nandfs.c ($(wc -l < "$C" | tr -d " ") lines) names no part of any machine"
