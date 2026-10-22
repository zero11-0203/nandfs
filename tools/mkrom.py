#!/usr/bin/env python3
"""Wrap one file as a ROM image for the RV32IM machine (read by sw/rt/rt.c).

    mkrom.py FILE OUT.rom

Header (64 bytes): b"ROMFILE\\0", size (u32 little endian), name (NUL-terminated).
"""
import struct
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
data = src.read_bytes()
name = src.name.encode()
assert len(name) < 52
header = b"ROMFILE\0" + struct.pack("<I", len(data)) + name
out.write_bytes(header.ljust(64, b"\0") + data)
