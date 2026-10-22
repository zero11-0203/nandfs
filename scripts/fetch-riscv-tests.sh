#!/bin/sh
# Download riscv-tests (BSD-3-Clause, https://github.com/riscv-software-src/riscv-tests)
# into $NANDFS_BUILD/riscv-tests; sw/isa builds rv32ui and rv32um from it.
set -eu
DEST=${NANDFS_BUILD:-$HOME/nandfs-build}/riscv-tests
COMMIT=3df703cd52d5f0d8224e3c50bf03c6cb70efff98
if [ ! -d "$DEST" ]; then
    git clone -q https://github.com/riscv-software-src/riscv-tests.git "$DEST"
fi
git -C "$DEST" fetch -q --depth 1 origin "$COMMIT" 2>/dev/null || true
git -C "$DEST" checkout -q "$COMMIT"
echo "riscv-tests $COMMIT in $DEST"
