# DOOM (doomgeneric) for the RV32IM folder computer. Fetch the sources first
# with scripts/fetch-doom.sh. Builds $(OUT)/doom.bin (RAM image) and
# $(OUT)/doom1.rom (the WAD with a ROM file header), and $(OUT)/doomplay.bin,
# the playable build (no demo; game clock PLAY_SLOWDOWN times slower).
BUILD ?= $(or $(NANDFS_BUILD),$(HOME)/nandfs-build)
OUT ?= $(BUILD)/sw
DG = $(BUILD)/doom/doomgeneric/doomgeneric
RT = ../rt
include ../rt/rt.mk

SRC_DOOM = dummy am_map doomdef doomstat dstrings d_event d_items d_iwad d_loop d_main d_mode \
  d_net f_finale f_wipe g_game hu_lib hu_stuff info i_cdmus i_endoom i_joystick i_scale i_sound \
  i_system i_timer memio m_argv m_bbox m_cheat m_config m_controls m_fixed m_menu m_misc m_random \
  p_ceilng p_doors p_enemy p_floor p_inter p_lights p_map p_maputl p_mobj p_plats p_pspr p_saveg \
  p_setup p_sight p_spec p_switch p_telept p_tick p_user r_bsp r_data r_draw r_main r_plane r_segs \
  r_sky r_things sha1 sounds statdump st_lib st_stuff s_sound tables v_video wi_stuff w_checksum \
  w_file w_main w_wad z_zone i_input i_video doomgeneric
OBJ = $(OUT)/doomobj
OBJS = $(addprefix $(OBJ)/, $(addsuffix .o, $(SRC_DOOM))) $(OBJ)/doomgeneric_nandfs.o $(OBJ)/w_file_rom.o $(OBJ)/rt.o
DOOM_CFLAGS = $(RT_CFLAGS) -I$(DG) -DDOOMGENERIC_RESX=320 -DDOOMGENERIC_RESY=200 -DCMAP256 \
  -DNORMALUNIX -D_DEFAULT_SOURCE -w

PLAY_SLOWDOWN ?= 40

all: $(OUT)/doom.bin $(OUT)/doomplay.bin $(OUT)/doom1.rom

$(OBJ)/%.o: $(DG)/%.c
	@mkdir -p $(OBJ)
	@$(CC) $(DOOM_CFLAGS) -c $< -o $@
$(OBJ)/%.o: %.c ../rt/machine.h ../rt/rom.h
	@mkdir -p $(OBJ)
	$(CC) $(DOOM_CFLAGS) -c $< -o $@
$(OBJ)/rt.o: ../rt/rt.c ../rt/machine.h
	@mkdir -p $(OBJ)
	$(CC) $(RT_CFLAGS) -c $< -o $@

$(OUT)/doom.elf: $(OBJS)
	$(CC) $(RT_CFLAGS) $(RT_LDFLAGS) -o $@ $(OBJS) -lm
	$(CROSS)size $@

$(OUT)/doom.bin: $(OUT)/doom.elf
	$(OBJCOPY) -O binary $< $@

$(OBJ)/doomgeneric_play.o: doomgeneric_nandfs.c ../rt/machine.h Makefile
	@mkdir -p $(OBJ)
	$(CC) $(DOOM_CFLAGS) -DPLAY_SLOWDOWN=$(PLAY_SLOWDOWN) -c $< -o $@
$(OUT)/doomplay.elf: $(filter-out $(OBJ)/doomgeneric_nandfs.o, $(OBJS)) $(OBJ)/doomgeneric_play.o
	$(CC) $(RT_CFLAGS) $(RT_LDFLAGS) -o $@ $^ -lm
$(OUT)/doomplay.bin: $(OUT)/doomplay.elf
	$(OBJCOPY) -O binary $< $@

$(OUT)/doom1.rom: $(BUILD)/doom/doom1.wad
	python3 ../../tools/mkrom.py $< $@
