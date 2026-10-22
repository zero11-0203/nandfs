CFLAGS ?= -O2 -g -Wall -Wextra -Wno-format-truncation
ifeq ($(shell uname),Darwin)
# macFUSE: its libfuse3 lives in /usr/local; ask for the portable libfuse API.
export PKG_CONFIG_PATH := /usr/local/lib/pkgconfig:$(PKG_CONFIG_PATH)
CFLAGS += -DFUSE_DARWIN_ENABLE_EXTENSIONS=0 -Wno-unknown-warning-option
endif
FUSE_CFLAGS := $(shell pkg-config --cflags fuse3)
FUSE_LIBS := $(shell pkg-config --libs fuse3)

# The source folder may be shared between machines (a Mac and a Linux VM), so
# each platform gets its own build directory.
BIN := bin/$(shell uname -s)-$(shell uname -m)

all: $(BIN)/nandfs

$(BIN)/nandfs: nandfs.c
	@mkdir -p $(BIN)
	$(CC) $(CFLAGS) $(FUSE_CFLAGS) -o $@ $< $(FUSE_LIBS)

clean:
	rm -rf bin
