# riscv-tests rv32ui and rv32um for the RV32IM folder computer. Fetch the
# sources with scripts/fetch-riscv-tests.sh. Left out: ma_data (misaligned
# accesses) and fence_i (Zifencei), which PicoRV32 does not implement.
BUILD ?= $(or $(NANDFS_BUILD),$(HOME)/nandfs-build)
OUT ?= $(BUILD)/sw/isa
RT = $(BUILD)/riscv-tests/isa
CROSS ?= riscv64-unknown-elf-
UI = simple add addi and andi auipc beq bge bgeu blt bltu bne jal jalr lb lbu lh lhu \
     lw ld_st lui or ori sb sh sll slli slt slti sltiu sltu sra srai srl srli st_ld sub sw xor xori
UM = div divu mul mulh mulhsu mulhu rem remu
TESTS = $(addprefix rv32ui-,$(UI)) $(addprefix rv32um-,$(UM)) mmio timing

all: $(addprefix $(OUT)/,$(addsuffix .bin,$(TESTS)))
	@echo $(TESTS) | tr ' ' '\n' > $(OUT)/list.txt

$(OUT)/%.elf: link.ld riscv_test.h
	@mkdir -p $(OUT)
	$(CROSS)gcc -march=rv32im -mabi=ilp32 -nostdlib -nostartfiles -T link.ld -I. \
	  -I$(RT)/macros/scalar -o $@ $(RT)/$(word 1,$(subst -, ,$*))/$(word 2,$(subst -, ,$*)).S

$(OUT)/%.bin: $(OUT)/%.elf
	$(CROSS)objcopy -O binary $< $@

$(OUT)/mmio.elf: mmio.S link.ld
	@mkdir -p $(OUT)
	$(CROSS)gcc -march=rv32im -mabi=ilp32 -nostdlib -nostartfiles -T link.ld -o $@ $<

$(OUT)/timing.elf: timing.S link.ld
	@mkdir -p $(OUT)
	$(CROSS)gcc -march=rv32im -mabi=ilp32 -nostdlib -nostartfiles -T link.ld -o $@ $<

.PRECIOUS: $(OUT)/%.elf
