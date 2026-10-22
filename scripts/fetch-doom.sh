#!/bin/sh
# Download doomgeneric (GPL-2.0, https://github.com/ozkl/doomgeneric) and the
# shareware DOOM 1.9 WAD (freely redistributable shareware episode) into
# $NANDFS_BUILD/doom. Neither is included in this repository.
set -eu
DEST=${NANDFS_BUILD:-$HOME/nandfs-build}/doom
COMMIT=e257a09527062bfb986b6e5e0780839b6cbd5b71
WAD_SHA1=5b2e249b9c5133ec987b3ea77596381dc0d6bc1d
mkdir -p "$DEST"
cd "$DEST"
if [ ! -d doomgeneric ]; then
    git clone -q https://github.com/ozkl/doomgeneric.git
fi
git -C doomgeneric checkout -q "$COMMIT"
if ! echo "$WAD_SHA1  doom1.wad" | sha1sum -c --status 2>/dev/null; then
    curl -fsSL -o doom1.wad https://github.com/Akbar30Bill/DOOM_wads/raw/master/doom1.wad
    echo "$WAD_SHA1  doom1.wad" | sha1sum -c --quiet
fi
echo "doomgeneric $COMMIT and doom1.wad in $DEST"
