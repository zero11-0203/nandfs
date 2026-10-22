#!/bin/sh
# run-doom.sh [--resume]: run DOOM (-timedemo demo1) on the RV32IM folder
# computer, saving every frame to $NANDFS_BUILD/doom-run/frames and comparing
# each with the reference model's. Runs for days; safe to stop and resume.
# Build first: scripts/fetch-doom.sh && scripts/build-rv32.sh
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
MNT=$OUT/doom-mnt
RUN=$OUT/doom-run
if [ ! -d "$OUT/ref-frames" ]; then
    mkdir -p "$OUT/ref-frames"
    "$OUT/rvref" -f "$OUT/ref-frames" "$OUT/sw/doom.bin" "$OUT/sw/doom1.rom" >/dev/null
fi
"$SRC/scripts/mount.sh" "$OUT/rvtree" "$MNT"
trap '"$SRC/scripts/unmount.sh" "$MNT"' EXIT
if [ "${1:-}" = --resume ]; then
    python3 -u "$SRC/viewer/rvdoom.py" "$MNT" "$RUN" --resume --ref "$OUT/ref-frames"
else
    rm -rf "$RUN"
    python3 -u "$SRC/viewer/rvdoom.py" "$MNT" "$RUN" --ram "$OUT/sw/doom.bin" \
        --rom "$OUT/sw/doom1.rom" --ref "$OUT/ref-frames"
fi
