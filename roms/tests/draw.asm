; CLS and DXYN: wrapping start, clipping at both edges, collision.
        CLS
        LD V0, 0
        LD V1, 0
        LD I, box
        DRW V0, V1, 4
        DRW V0, V1, 4       ; erases: collision
        LD V0, 60
        LD V1, 30
        DRW V0, V1, 4       ; clipped right and bottom
        LD V0, 66           ; start wraps to x 2
        LD V1, 33           ; and y 1
        DRW V0, V1, 4
        LD V2, 0
        LD V3, 10
        LD V4, 0
digits: LD F, V4
        DRW V2, V3, 5
        ADD V2, 5
        ADD V4, 1
        SE V4, 16
        JP digits
        LD V0, 5
        LD VF, 12
        LD I, box
        DRW VF, V0, 3       ; VF as the x coordinate
        DRW V0, VF, 0       ; N = 0 draws nothing
        LD I, tall
        LD V5, 20
        DRW V5, V5, 15
        CLS
        DRW V5, V5, 15
end:    JP end
box:    db 0xFF, 0x81, 0x81, 0xFF
tall:   db 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
        db 0xFF, 0x00, 0xAA, 0x55, 0x0F, 0xF0, 0x3C
