# Software for the RV32IM folder computer. Output in $(OUT).
BUILD ?= $(or $(NANDFS_BUILD),$(HOME)/nandfs-build)
OUT ?= $(BUILD)/sw
RT = rt
include rt/rt.mk

all: $(OUT)/hello.bin

$(OUT)/%.elf: tests/%.c rt/rt.c rt/machine.h
	@mkdir -p $(OUT)
	$(CC) $(RT_CFLAGS) $(RT_LDFLAGS) -o $@ tests/$*.c rt/rt.c

$(OUT)/%.bin: $(OUT)/%.elf
	$(OBJCOPY) -O binary $< $@

.PRECIOUS: $(OUT)/%.elf
