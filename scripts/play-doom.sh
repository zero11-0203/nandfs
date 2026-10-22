#!/bin/sh
# play-doom.sh [--resume]: play DOOM on the RV32IM folder computer in a web
# browser (http://localhost:8035). Starts in E1M1; a frame takes two or
# three minutes. Ctrl-C saves the machine; --resume continues from the save,
# which also skips the boot.
# Build first: scripts/fetch-doom.sh && scripts/build-rv32.sh
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
OUT=${NANDFS_BUILD:-$HOME/nandfs-build}
MNT=$OUT/play-mnt
RUN=$OUT/play-run
TREE=$OUT/play-tree
# A copy of the machine's folders of its own: the RAM file lives in the
# backing tree, so sharing rvtree with run-doom.sh would mix the two games.
if [ ! -d "$TREE" ] || [ "$OUT/rvtree" -nt "$TREE" ]; then
    rm -rf "$TREE"
    cp -a "$OUT/rvtree" "$TREE"
fi
"$SRC/scripts/mount.sh" "$TREE" "$MNT"
trap '"$SRC/scripts/unmount.sh" "$MNT"' EXIT
if [ "${1:-}" = --resume ]; then
    python3 -u "$SRC/viewer/rvplay.py" "$MNT" "$RUN" --resume
else
    rm -rf "$RUN"
    python3 -u "$SRC/viewer/rvplay.py" "$MNT" "$RUN" --ram "$OUT/sw/doomplay.bin" \
        --rom "$OUT/sw/doom1.rom"
fi
