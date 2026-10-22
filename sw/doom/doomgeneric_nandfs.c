/* doomgeneric platform for the RV32IM folder computer.
 *
 * Video: DOOM's 320x200 8-bit frame goes to MACHINE_FB and its palette to
 * MACHINE_PALETTE; MACHINE_FRAME counts finished frames so the viewer knows
 * when to grab one. (Built with CMAP256: converting every pixel to RGB here
 * would cost the CPU 2 million instructions a frame.)
 * Time: the TIME register, a millisecond counter built from gates. The
 * playable build (-DPLAY_SLOWDOWN=N) runs the game clock N times slower than
 * TIME, so that the world advances about one tic per drawn frame.
 * Input: the KEYS register; each bit is one key pin (see keymap).
 * The WAD is the file in the ROM (see rt/rt.c). */
#include <stdio.h>
#include <string.h>
#include "doomgeneric.h"
#include "doomkeys.h"
#include "i_video.h"
#include "machine.h"

static const unsigned char keymap[] = {
    KEY_UPARROW, KEY_DOWNARROW, KEY_LEFTARROW, KEY_RIGHTARROW,
    KEY_FIRE, KEY_USE, KEY_RSHIFT, KEY_ENTER, KEY_ESCAPE, 'y',
    KEY_STRAFE_L, KEY_STRAFE_R, KEY_TAB,
};
#define NKEYS (sizeof keymap / sizeof keymap[0])

static uint32_t keys_reported;

void DG_Init(void) {
    DG_ScreenBuffer = MACHINE_FB;
    MACHINE_FRAME = 0;
}

void DG_DrawFrame(void) {
    memcpy(MACHINE_PALETTE, colors, sizeof colors);
    MACHINE_FRAME = MACHINE_FRAME + 1;
}

#ifdef PLAY_SLOWDOWN
uint32_t DG_GetTicksMs(void) { return MACHINE_TIME / PLAY_SLOWDOWN; }

void DG_SleepMs(uint32_t ms) {
    uint32_t t0 = DG_GetTicksMs();
    while (DG_GetTicksMs() - t0 < ms) {
    }
}
#else
void DG_SleepMs(uint32_t ms) {
    uint32_t t0 = MACHINE_TIME;
    while (MACHINE_TIME - t0 < ms) {
    }
}

uint32_t DG_GetTicksMs(void) { return MACHINE_TIME; }
#endif

int DG_GetKey(int *pressed, unsigned char *key) {
    uint32_t now = MACHINE_KEYS, changed = now ^ keys_reported;
    for (unsigned i = 0; i < NKEYS; i++)
        if (changed >> i & 1) {
            keys_reported ^= 1u << i;
            *pressed = now >> i & 1;
            *key = keymap[i];
            return 1;
        }
    return 0;
}

void DG_SetWindowTitle(const char *title) { (void)title; }

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;
#ifdef PLAY_SLOWDOWN
    /* Playable: straight into E1M1 on "Hurt me plenty"; Esc opens the menu. */
    static char *args[] = { "doom", "-iwad", "doom1.wad", "-nosound", "-warp", "1", "1",
                            "-skill", "3", NULL };
#else
    /* -timedemo plays the first demo, drawing every game tic, as fast as the
     * machine can, then prints how long it took and exits. */
    static char *args[] = { "doom", "-iwad", "doom1.wad", "-nosound", "-timedemo", "demo1", NULL };
#endif
    doomgeneric_Create(sizeof args / sizeof args[0] - 1, args);
    for (;;) doomgeneric_Tick();
}
