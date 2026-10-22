; Pong for the nandfs CHIP-8. You are the left paddle: key 1 moves up and
; key 4 moves down (keyboard 1 and Q). The right paddle follows the ball.
;
; Written for the COSMAC VIP display-wait quirk: every DRW waits for the next
; 60 Hz frame, so each pass through the loop draws exactly two sprites (the
; ball and one paddle, or a do-nothing DRW with zero rows) and the game runs at
; an even 30 steps per second.
;
; V0 left paddle top    V1 right paddle top   V2,V3 ball x,y   V4,V5 ball dx,dy
; V6 left score         V7 right score        VA,VB paddle columns
; VC which paddle moves this pass             V8,V9,VD,VE,VF scratch

        CLS
        LD V6, 0
        LD V7, 0
        LD V0, 13
        LD V1, 13
        LD VA, 2
        LD VB, 61
        LD VC, 0
        LD I, paddle
        DRW VA, V0, 6
        DRW VB, V1, 6
        CALL score

serve:  LD V2, 32
        RND V3, 15
        ADD V3, 8
        RND V4, 2           ; dx: +1 or -1
        LD V8, 0xFF
        SE V4, 0
        LD V8, 1
        LD V4, V8
        RND V5, 1           ; dy: +1 or -1
        LD V8, 0xFF
        SE V5, 0
        LD V8, 1
        LD V5, V8
        LD I, dot
        DRW V2, V3, 1

loop:   SNE V3, 0           ; bounce off the top and bottom walls
        LD V5, 1
        SNE V3, 31
        LD V5, 0xFF
        SNE V2, 3           ; next to the left paddle?
        CALL hit_left
        SNE V2, 60          ; next to the right paddle?
        CALL hit_right
        SNE V2, 0
        JP right_scores
        SNE V2, 63
        JP left_scores
        CALL move_ball
        LD V8, 1            ; paddles take turns
        XOR VC, V8
        SE VC, 0
        JP move_right

move_left:
        LD V8, 1
        SKNP V8
        JP left_up
        LD V8, 4
        SKNP V8
        JP left_down
idle:   DRW V0, V0, 0       ; zero rows: just wait for the frame
        JP loop
left_up:
        SNE V0, 0
        JP idle
        ADD V0, 0xFF
        LD I, step
        DRW VA, V0, 7       ; light the new top, clear the old bottom
        JP loop
left_down:
        SNE V0, 26
        JP idle
        LD I, step
        DRW VA, V0, 7       ; clear the old top, light the new bottom
        ADD V0, 1
        JP loop

move_right:
        LD V8, V1           ; up if the ball is above paddle row 2
        ADD V8, 2
        LD V9, V3
        SUB V9, V8
        SE VF, 1
        JP right_up
        LD V8, V1           ; down if it is below paddle row 3
        ADD V8, 3
        LD V9, V8
        SUB V9, V3
        SE VF, 1
        JP right_down
        JP idle
right_up:
        SNE V1, 0
        JP idle
        ADD V1, 0xFF
        LD I, step
        DRW VB, V1, 7
        JP loop
right_down:
        SNE V1, 26
        JP idle
        LD I, step
        DRW VB, V1, 7
        ADD V1, 1
        JP loop

; Move the ball one pixel diagonally with a single two-row sprite that turns
; the old pixel off and the new one on.
move_ball:
        LD V8, V2
        LD V9, V3
        ADD V2, V4
        ADD V3, V5
        LD VD, V8           ; sprite corner: the smaller x and y
        SE V4, 1
        LD VD, V2
        LD VE, V9
        SE V5, 1
        LD VE, V3
        LD I, diag_a
        SE V4, V5
        LD I, diag_b
        DRW VD, VE, 2
        RET

hit_left:
        SE V4, 0xFF         ; only when moving left
        RET
        LD V8, V3
        SUB V8, V0          ; V8 = ball row - paddle top
        SE VF, 1
        RET                 ; ball is above the paddle
        LD V9, 6
        SUBN V9, V8
        SE VF, 0
        RET                 ; ball is below the paddle
        LD V4, 1
        RET

hit_right:
        SE V4, 1            ; only when moving right
        RET
        LD V8, V3
        SUB V8, V1
        SE VF, 1
        RET
        LD V9, 6
        SUBN V9, V8
        SE VF, 0
        RET
        LD V4, 0xFF
        RET

right_scores:
        CALL score          ; erase the old score
        ADD V7, 1
        JP point
left_scores:
        CALL score
        ADD V6, 1
point:  CALL score
        LD I, dot
        DRW V2, V3, 1       ; erase the ball
        JP serve

score:  LD F, V6
        LD V8, 24
        LD V9, 1
        DRW V8, V9, 5
        LD F, V7
        LD V8, 36
        DRW V8, V9, 5
        RET

paddle: db 0x80, 0x80, 0x80, 0x80, 0x80, 0x80
dot:    db 0x80
diag_a: db 0x80, 0x40
diag_b: db 0x40, 0x80
step:   db 0x80, 0, 0, 0, 0, 0, 0x80
