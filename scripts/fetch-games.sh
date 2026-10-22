#!/bin/sh
# Download games from John Earnest's Chip8 Community Archive into build/games.
# Everything in that archive is CC0 ("No Rights Reserved"):
#   https://github.com/JohnEarnest/chip8Archive
# These run correctly with the COSMAC VIP quirks this machine implements.
set -eu
DEST=${1:-$(dirname "$0")/../build/games}
mkdir -p "$DEST"
COMMIT=761e3ffc63f43e6a849e80714122feff2afca208
BASE=https://raw.githubusercontent.com/JohnEarnest/chip8Archive/$COMMIT/roms
for g in dinorun wdl knumberknower chipquarium br8kout ghostEscape tombstontipp \
         mini-lights-out RPS octorancher down8 flightrunner; do
    curl -fsSL -o "$DEST/$g.ch8" "$BASE/$g.ch8"
done
ls "$DEST"
