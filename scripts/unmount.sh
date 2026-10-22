#!/bin/sh
# unmount.sh MOUNTPOINT: unmount a folder computer (Linux or macOS).
fusermount3 -u "$1" 2>/dev/null || umount "$1" 2>/dev/null || true
