#!/usr/bin/env python3
"""A small CHIP-8 assembler using the classic mnemonics (Cowgod's reference).

    c8asm.py SOURCE.asm OUT.ch8

    loop:  LD V0, 0x12      ; comments start with ;
           ADD V0, V1
           LD I, sprite
           DRW V0, V1, 5
           JP loop
    sprite: db 0xF0, 0x90, 0b10010000, 0x90, 0xF0

Numbers are decimal, 0x hex, #hex or 0b binary. Programs start at 0x200.
"""
import re
import sys


def num(s, labels):
    s = s.strip()
    if s in labels:
        return labels[s]
    if s.startswith("#"):
        return int(s[1:], 16)
    return int(s, 0)


def reg(s):
    m = re.fullmatch(r"[Vv]([0-9a-fA-F])", s.strip())
    return int(m.group(1), 16) if m else None


def encode(op, args, labels):
    A = [a.strip() for a in args]
    U = [a.upper() for a in A]
    r = [reg(a) for a in A]
    n = lambda k: num(A[k], labels)
    if op == "CLS": return 0x00E0
    if op == "RET": return 0x00EE
    if op == "SYS": return n(0) & 0xFFF
    if op == "JP":
        if len(A) == 2 and U[0] == "V0":
            return 0xB000 | n(1)
        return 0x1000 | n(0)
    if op == "CALL": return 0x2000 | n(0)
    if op in ("SE", "SNE"):
        if r[1] is not None:
            return (0x5000 if op == "SE" else 0x9000) | r[0] << 8 | r[1] << 4
        return (0x3000 if op == "SE" else 0x4000) | r[0] << 8 | (n(1) & 0xFF)
    if op == "LD":
        if U[0] == "I": return 0xA000 | n(1)
        if U[0] == "DT": return 0xF015 | r[1] << 8
        if U[0] == "ST": return 0xF018 | r[1] << 8
        if U[0] == "F": return 0xF029 | r[1] << 8
        if U[0] == "B": return 0xF033 | r[1] << 8
        if U[0] == "[I]": return 0xF055 | r[1] << 8
        if U[1] == "DT": return 0xF007 | r[0] << 8
        if U[1] == "K": return 0xF00A | r[0] << 8
        if U[1] == "[I]": return 0xF065 | r[0] << 8
        if r[1] is not None: return 0x8000 | r[0] << 8 | r[1] << 4
        return 0x6000 | r[0] << 8 | (n(1) & 0xFF)
    if op == "ADD":
        if U[0] == "I": return 0xF01E | r[1] << 8
        if r[1] is not None: return 0x8004 | r[0] << 8 | r[1] << 4
        return 0x7000 | r[0] << 8 | (n(1) & 0xFF)
    alu = {"OR": 1, "AND": 2, "XOR": 3, "SUB": 5, "SHR": 6, "SUBN": 7, "SHL": 0xE}
    if op in alu:
        y = r[1] if len(A) > 1 else r[0]
        return 0x8000 | r[0] << 8 | y << 4 | alu[op]
    if op == "RND": return 0xC000 | r[0] << 8 | (n(1) & 0xFF)
    if op == "DRW": return 0xD000 | r[0] << 8 | r[1] << 4 | (n(2) & 15)
    if op == "SKP": return 0xE09E | r[0] << 8
    if op == "SKNP": return 0xE0A1 | r[0] << 8
    raise ValueError(f"unknown instruction {op}")


def assemble(src):
    lines = []
    for ln, raw in enumerate(src.splitlines(), 1):
        text = raw.split(";")[0].strip()
        while ":" in text.split(" ")[0]:
            label, text = text.split(":", 1)
            lines.append((ln, "label", label.strip(), []))
            text = text.strip()
        if text:
            parts = text.split(None, 1)
            args = [a for a in re.split(r",", parts[1])] if len(parts) > 1 else []
            lines.append((ln, parts[0].upper(), None, args))
    for pass_ in (0, 1):
        labels = labels if pass_ else {}
        out, pc = bytearray(), 0x200
        for ln, op, label, args in lines:
            try:
                if op == "label":
                    labels[label] = pc
                elif op == "DB":
                    for a in args:
                        out.append(num(a, labels) & 0xFF if pass_ else 0)
                elif op == "DW":
                    for a in args:
                        w = num(a, labels) if pass_ else 0
                        out += bytes([w >> 8 & 0xFF, w & 0xFF])
                else:
                    w = encode(op, args, labels) if pass_ else 0
                    out += bytes([w >> 8, w & 0xFF])
            except Exception as e:
                if pass_:
                    raise SystemExit(f"line {ln}: {e}")
            pc = 0x200 + len(out)
    return bytes(out)


if __name__ == "__main__":
    open(sys.argv[2], "wb").write(assemble(open(sys.argv[1]).read()))
