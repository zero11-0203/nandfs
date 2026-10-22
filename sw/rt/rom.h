/* The file stored in the ROM. rom_file(name, &size) returns its data if the
 * ROM holds a file called name (or any file, if name is NULL), else NULL. */
#ifndef ROM_H
#define ROM_H
const unsigned char *rom_file(const char *name, unsigned int *size);
#endif
