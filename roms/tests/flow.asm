; Jumps, calls, returns, all four skips, BNNN and nested calls.
        LD V0, 4
        LD V1, 4
        LD V2, 9
        SE V0, 4
        LD V3, 1            ; skipped
        SE V0, 5
        LD V3, 2
        SNE V0, 4
        LD V4, 3
        SNE V0, 7
        LD V4, 4            ; skipped
        SE V0, V1
        LD V5, 5            ; skipped
        SE V0, V2
        LD V5, 6
        SNE V0, V2
        LD V6, 7            ; skipped
        SNE V0, V1
        LD V6, 8
        CALL sub1
        LD V0, 2
        JP V0, table        ; BNNN: table + 2
table:  JP bad
        JP good
bad:    LD V7, 0xBB
good:   LD V7, 0x60
        CALL deep
end:    JP end
sub1:   LD V8, 0x11
        CALL sub2
        ADD V8, 1
        RET
sub2:   LD V9, 0x22
        RET
deep:   ADD VA, 1
        SE VA, 14
        CALL deep
        RET
