#include <stdio.h>
#include <stdlib.h>
#include "machine.h"

int main(void) {
    printf("hello from RV32IM, %d * %d = %d, 1000/7 = %d\n", 123, 456, 123 * 456, 1000 / 7);
    char *p = malloc(100000);
    printf("malloc %p, time %u ms\n", p, (unsigned)MACHINE_TIME);
    return 3;
}
