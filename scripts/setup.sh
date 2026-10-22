#!/bin/sh
# setup.sh [rv32]: install what nandfs needs on Debian/Ubuntu, then build.
# Afterwards, scripts/play.sh plays Pong. With "rv32", also install the RISC-V
# cross compiler, fetch PicoRV32, riscv-tests, doomgeneric and the shareware
# WAD, and build the RISC-V machine and DOOM.
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
PKGS="build-essential pkg-config libfuse3-dev fuse3 yosys iverilog python3 curl git ffmpeg"
if [ "${1:-}" = rv32 ]; then
    PKGS="$PKGS gcc-riscv64-unknown-elf picolibc-riscv64-unknown-elf"
fi
if command -v apt-get >/dev/null; then
    missing=""
    for p in $PKGS; do
        dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"
    done
    if [ -n "$missing" ]; then
        echo "installing:$missing"
        sudo apt-get update -qq
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $missing
    fi
else
    echo "not a Debian/Ubuntu system: install these yourself: $PKGS"
fi
[ -e /dev/fuse ] || { echo "no /dev/fuse: this machine cannot mount FUSE filesystems"; exit 1; }
"$SRC/scripts/fetch-roms.sh" >/dev/null
"$SRC/scripts/fetch-games.sh" >/dev/null
"$SRC/scripts/build.sh"
if [ "${1:-}" = rv32 ]; then
    "$SRC/scripts/fetch-doom.sh"
    "$SRC/scripts/build-rv32.sh"
fi
echo
echo "ready. play Pong with:   scripts/play.sh"
echo "or another game:          scripts/play.sh build/games/br8kout.ch8"
if [ "${1:-}" = rv32 ]; then
    echo "play DOOM (slowly):       scripts/play-doom.sh"
fi
