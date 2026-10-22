/* The RV32IM folder computer, as seen by software (see tools/rvref.c). */
#ifndef MACHINE_H
#define MACHINE_H
#include <stdint.h>

#define MACHINE_TIME (*(volatile uint32_t *)0x20000000)   /* ms since reset */
#define MACHINE_KEYS (*(volatile uint32_t *)0x20000004)   /* key pins */
#define MACHINE_ROM ((const uint8_t *)0x10000000)

/* Software conventions the viewer and rvref know about. */
#define MACHINE_FB ((uint8_t *)0x00E00000)                 /* 320x200 indexed */
#define MACHINE_PALETTE ((uint32_t *)0x00E10000)           /* 256 x 0x00RRGGBB */
#define MACHINE_FRAME (*(volatile uint32_t *)0x00DFFFF0)  /* frames finished */
#define MACHINE_CONSOLE ((volatile uint32_t *)0x00F00000)  /* length, then text */
#define MACHINE_CONSOLE_MAX 0xFFFFC

#endif
