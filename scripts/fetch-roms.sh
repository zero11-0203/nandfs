#!/bin/sh
# Download third-party test ROMs into build/roms (not committed).
#   Timendus chip8-test-suite v4.1, GPL-3.0: https://github.com/Timendus/chip8-test-suite
set -eu
DEST=${1:-$(dirname "$0")/../build/roms}
mkdir -p "$DEST"
BASE=https://raw.githubusercontent.com/Timendus/chip8-test-suite/v4.1/bin
for f in 1-chip8-logo 2-ibm-logo 3-corax+ 4-flags 5-quirks 6-keypad; do
    curl -fsSL -o "$DEST/$f.ch8" "$BASE/$f.ch8"
done
ls -l "$DEST"
