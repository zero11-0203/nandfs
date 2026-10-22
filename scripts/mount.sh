#!/bin/sh
# mount.sh BACKING MOUNTPOINT: mount a folder computer.
set -eu
SRC=$(cd "$(dirname "$0")/.." && pwd)
make -s -C "$SRC/fs"
NANDFS=$SRC/fs/bin/$(uname -s)-$(uname -m)/nandfs
mkdir -p "$2"
"$SRC/scripts/unmount.sh" "$2"
if [ "$(uname -s)" = Darwin ]; then
    # Without this, macOS stores extended attributes as ._ files in the tree.
    "$NANDFS" "$1" "$2" -o noappledouble
else
    "$NANDFS" "$1" "$2"
fi
