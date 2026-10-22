# Build rules for programs on the RV32IM folder computer. Include from a
# Makefile after setting RT to this directory.
CROSS ?= riscv64-unknown-elf-
CC = $(CROSS)gcc
OBJCOPY = $(CROSS)objcopy
ARCH = -march=rv32im -mabi=ilp32
# Code and constants from 0, data/bss/heap from 4 MB, stack ends at 0xDF0000.
LAYOUT = -Wl,--defsym=__flash=0 -Wl,--defsym=__flash_size=0x400000 \
         -Wl,--defsym=__ram=0x400000 -Wl,--defsym=__ram_size=0x9F0000 \
         -Wl,--defsym=__stack_size=0x100000
RT_CFLAGS = $(ARCH) --specs=picolibc.specs --crt0=hosted -O2 -I$(RT) -ffunction-sections -fdata-sections
RT_LDFLAGS = $(LAYOUT) -Wl,-Map=$@.map

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
