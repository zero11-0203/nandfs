// WAD access for the RV32IM folder computer: the WAD is the file in the ROM
// (see rt/rt.c), so a read is a memcpy. Replaces w_file_stdc.c, under the
// same class name. Lumps are copied rather than mapped because they are not
// all aligned and the CPU has no misaligned loads.
#include <string.h>

#include "w_file.h"
#include "z_zone.h"
#include "rom.h"

extern wad_file_class_t stdc_wad_file;

static wad_file_t *W_Rom_OpenFile(char *path)
{
    const char *base = strrchr(path, '/');
    unsigned int size;
    const unsigned char *data = rom_file(base ? base + 1 : path, &size);
    wad_file_t *result;

    if (data == NULL)
    {
        return NULL;
    }
    result = Z_Malloc(sizeof(wad_file_t), PU_STATIC, 0);
    result->file_class = &stdc_wad_file;
    result->mapped = NULL;
    result->length = size;
    return result;
}

static void W_Rom_CloseFile(wad_file_t *wad)
{
    Z_Free(wad);
}

size_t W_Rom_Read(wad_file_t *wad, unsigned int offset,
                  void *buffer, size_t buffer_len)
{
    unsigned int size;
    const unsigned char *data = rom_file(NULL, &size);

    if (offset >= size)
    {
        return 0;
    }
    if (buffer_len > size - offset)
    {
        buffer_len = size - offset;
    }
    memcpy(buffer, data + offset, buffer_len);
    return buffer_len;
}

wad_file_class_t stdc_wad_file =
{
    W_Rom_OpenFile,
    W_Rom_CloseFile,
    W_Rom_Read,
};
