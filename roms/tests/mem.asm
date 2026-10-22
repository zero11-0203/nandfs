; ANNN, FX1E, FX33, FX55, FX65, FX29, and reading the font ROM.
        LD I, buf
        LD V0, 254
        LD B, V0            ; 2 5 4
        LD V2, [I]          ; V0..V2 = digits, I += 3
        LD V5, 0x10
        ADD I, V5
        LD V0, 1
        LD V1, 2
        LD V2, 3
        LD V3, 4
        LD [I], V3          ; store V0..V3, I += 4
        LD I, buf
        ADD I, V5
        LD VF, [I]          ; load 16 bytes into V0..VF
        LD V0, 0x0B
        LD F, V0            ; I = 0x0B * 5
        LD V3, [I]          ; first rows of the B sprite, from ROM
        LD VC, 0x7
        LD F, VC
        LD V0, [I]
        LD I, 0xFFE
        LD V1, 0x99
        LD V0, 0x88
        LD [I], V1          ; wraps from 0xFFF to 0x000
        LD I, 0xFFE
        LD V1, [I]
        LD V6, 0xF0
        LD I, 0xFFF
        ADD I, V6           ; I goes past 0xFFF
        LD V0, 0
        LD B, V0
        LD I, buf
        LD V7, 9
        LD B, V7
        LD V2, [I]
end:    JP end
buf:    db 0, 0, 0, 0, 0, 0, 0, 0
