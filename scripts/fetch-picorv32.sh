#!/bin/sh
# Download PicoRV32 (ISC license, https://github.com/YosysHQ/picorv32), the
# RV32IM CPU of the RISC-V folder computer, into $NANDFS_BUILD/picorv32.
set -eu
DEST=${NANDFS_BUILD:-$HOME/nandfs-build}/picorv32
COMMIT=ef203c2b0a3fb793280f5114941416c425c5b461
if [ ! -d "$DEST" ]; then
    git clone -q https://github.com/YosysHQ/picorv32.git "$DEST"
fi
git -C "$DEST" checkout -q "$COMMIT"
echo "picorv32 $COMMIT in $DEST"
