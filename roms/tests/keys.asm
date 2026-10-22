; EX9E, EXA1 and FX0A (waits for a key to be pressed and released).
        LD V0, 5
        LD V1, 0xA
poll:   SKP V0
        JP poll
        LD V2, 1
held:   SKNP V0
        JP held
        LD V2, 2
        LD V3, K
        LD V4, K
        SKNP V1
        LD V5, 7
        LD V6, 0x15         ; only the low digit picks the key
        SKP V6
        LD V7, 9
end:    JP end
