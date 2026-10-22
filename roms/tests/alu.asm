; 6XNN, 7XNN and every 8XYN, including VF as an operand and as the target.
        LD V0, 0x12
        LD V1, 0xF0
        ADD V0, 0xFF        ; 7XNN wraps, no flag
        LD V2, V1
        OR V2, V0
        AND V2, V0
        LD VF, 0x55
        XOR V2, V1          ; VF reset to 0
        LD V3, 0xC8
        LD V4, 0x64
        ADD V3, V4          ; carry
        ADD V3, V4          ; no carry
        LD V5, 0x10
        SUB V5, V4          ; borrow
        SUB V4, V5
        SUBN V5, V4
        SUBN V4, V4
        LD V6, 0x81
        SHR V7, V6          ; V7 = V6 >> 1, VF = 1
        SHL V8, V6          ; V8 = V6 << 1, VF = 1
        SHR V6, V6
        LD VF, 0x90
        ADD VF, V1          ; result replaced by the flag
        LD VF, 0x03
        SHL VF, VF
        LD VE, 0xFF
        LD VF, 0x01
        ADD VE, VF          ; VF used as operand
        LD VF, 0x10
        SUB VF, V0
        LD VA, 0x7F
        SUBN VA, VF
        LD V9, 0
loop:   ADD V9, 0x13
        LD VB, V9
        SHR VB, V9
        XOR VB, V9
        SE V9, 0x00
        JP loop
end:    JP end
