#!/bin/sh
# play.sh [ROM]: build if needed, mount the folder computer, and play.
# With no ROM, plays Pong (roms/pong.asm). The machine stays mounted at
# $NANDFS_BUILD/mnt until you quit, so you can explore it from another shell.
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
"$SRC/scripts/build.sh"
ROM=${1:-$SRC/build/pong.ch8}
MNT=$OUT/mnt
if ! mount | grep -q " $MNT "; then
    "$SRC/scripts/mount.sh" "$OUT/tree" "$MNT"
    trap '"$SRC/scripts/unmount.sh" "$MNT"' EXIT
    printf "loading the machine... "
    grep -E '^(nand|dff) ' "$MNT/.ctl/stats" | tr '\n' ' '
    echo
fi
python3 "$SRC/viewer/play.py" "$MNT" "$ROM"
