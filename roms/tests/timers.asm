; FX15, FX07, FX18 and CXNN: counting frames and drawing random numbers.
        LD V0, 30
        LD DT, V0
        LD ST, V0
wait:   LD V1, DT
        SE V1, 0
        JP wait
        LD V2, 5
        LD ST, V2
        RND V3, 0xFF
        RND V4, 0x0F
        RND V5, 0
        LD V6, 0
rand:   RND V7, 0xFF
        ADD V6, 1
        SE V6, 40
        JP rand
        LD V0, 3
        LD DT, V0
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
        LD V8, DT
end:    JP end
